from django.forms import ValidationError
from django.shortcuts import render
from django.http import HttpResponseNotFound
from django.core.validators import EmailValidator, ValidationError
from django.views import View
from .models import TopPosts, LatestPosts, Business, Sport, EmailList
from newsapi import NewsApiClient
from django.db.models import Count
from django.apps import apps
from .forms import EmailListForm
from django.contrib import messages
import re
from math import ceil
from django.core.paginator import Paginator
from django.core.files import File
import os
from django.conf import settings
from django.db.models import Max
from django.views.decorators.cache import cache_page




class NewsApiMixin:
    api_key = '5e6869c7f6e8463396a829465bff72a7'

    def __init__(self):
        self.newsapi = NewsApiClient(api_key=self.api_key)

    def get_top_articles(self, category):
        return self.newsapi.get_top_headlines(category=category, language='en')

    def get_everything(self, sources, language, sort_by):
        return self.newsapi.get_everything(sources=sources, language=language, sort_by=sort_by)


class AuthorImageProecessor:
    companies = {'BBC News': 'bbc.png',
                 'CNN': 'cnn.png',
                 'CBS Sports': 'cbs.png',
                 'Reuters': 'reuters.png',
                 'The Times of India': 'toi.png',
                 'YouTube': 'youtube.png',
                 'Hindustan Times': 'ht.png',
                 'NDTV News': 'ndtv.png',
                 'Daily Mail': 'dm.png',
                 'ESPN': 'espn.png',
                 'Financial Times': 'ft.png',
                 'Yahoo Entertainment': 'yahoo.png',
                 'Engadget': 'Engadget_Logo.png',
                 'Google News': 'google.png',
                 'Livemint': 'livemint-logo.png'}

    def getLogo(self, name):
        if name in self.companies:
            return self.companies[name]

    def getLogoFromModel(self, name):
        folder_path = folder_path = os.path.join(
            os.path.join(settings.BASE_DIR, 'app_news', 'static', 'app_news', 'img'))
        if name in self.companies:
            image_path = os.path.join(folder_path, self.companies[name])
            return File(open(image_path, 'rb'))
        else:
            return None


class ArticleProcessor:
    @staticmethod
    def process_and_save_articles(articles, model):
        if 'articles' in articles:
            articles = articles['articles']

            for article in articles:
                title = article['title'] or "No title available"
                description = article['description'] or article['content']
                source = article['source']['name'] or "No source available"
                url_img = article[
                              'urlToImage'] or "https://www.salonlfc.com/wp-content/uploads/2018/01/image-not-found-scaled-1150x647.png"
                url = article['url']
                category = model.__name__ if model.__name__ in (
                'LatestPosts', 'TopPosts', 'Business', 'Sport') else None
                textContent = str(article['content'])
                timeToRead = ArticleProcessor.calcuate_read_time(textContent, 200)
                # authorImg = AuthorImageProecessor().getLogoFromModel(source)

                # Use get_or_create() to avoid creating duplicate posts
                post, created = model.objects.get_or_create(
                    title=title,
                    defaults={
                        'author': source,
                        'main_image': url_img,
                        'excerpt': description,
                        'urlToPost': url,
                        'category': category,
                        'timeToRead': timeToRead,
                        # 'AuthorImg': authorImg
                    }
                )

                # If the post is newly created, save it
                if created:
                    try:
                        post.save()
                    except ValidationError as e:
                        print(
                            f"Failed to save post with title '{title}' to {model.__name__} due to validation error: {e}")
        else:
            print(f"No articles found for model {model.__name__}")

    @staticmethod
    def calcuate_read_time(text, wpm=200) -> int:
        # Extract the number of additional characters from the text
        additional_chars_match = re.search(r"\+(\d+) chars", text)
        if additional_chars_match:
            additional_chars = int(additional_chars_match.group(1))
        else:
            additional_chars = 0

        cleaned_text = re.sub(r"[^\w\s]|(\+\d+ chars)", "", text)

        partial_word_count = len(cleaned_text.split())

        avg_chars_per_word = 5

        total_word_count = partial_word_count + additional_chars / avg_chars_per_word

        minutes = total_word_count / wpm

        return ceil(minutes)


class IndexView(View):
    template_name = 'app_news/main.html'

    def dispatch(self, request, *args, **kwargs):
        return cache_page(300, cache='default')(super().dispatch)(request, *args, **kwargs)

    def get(self, request):
        # Retrieve the latest posts directly without querying the database
        all_posts = TopPosts.objects.order_by('-id')[:1].first()
        latest_posts = LatestPosts.objects.order_by('-id')[:4]
        business_posts = Business.objects.order_by('-id')[:2]
        sport_posts = Sport.objects.order_by('-id')[:2]

        # Get the author counts without hitting the database
        top_author = TopPosts.objects.values('author').annotate(count=Max('id')).order_by('-count')[:4]

        # Get the sorted list of authors
        sorted_authors = [item['author'] for item in top_author]

        form = EmailListForm()

        # Get the author images
        authorImgProcess = AuthorImageProecessor()
        authorImg = [authorImgProcess.getLogo(author) for author in sorted_authors]
        author_and_img = zip(sorted_authors, authorImg)

        context = {'posts': all_posts,
                   'latest': latest_posts,
                   'business': business_posts,
                   'sport': sport_posts,
                   'sorted_authors': sorted_authors,
                   'authorAndImg': author_and_img,
                   'form': form}

        return render(request, self.template_name, context)

    def post(self, request):
        email = request.POST.get('email')

        emial_validator = EmailValidator()
        try:
            emial_validator(email)
            email_is_valid = True
        except ValidationError:
            email_is_valid = False

        if email_is_valid:
            email_list, created = EmailList.objects.get_or_create(email=email)
            if created:
                messages.success(request, 'You have successfully subscribed to our newsletter!')
                email_list.save()
            else:
                messages.warning(request, 'You are already subscribed to our newsletter!')

            # request.session['subscribed'] = True
            # return HttpResponseRedirect(reverse('success'))
        else:
            messages.error(request, 'Please enter a valid email address!')
            # return HttpResponseRedirect(reverse('index'))

        return self.get(request)


class SpecificCategoryView(View):
    template_name = 'app_news/allPage.html'
    items_per_page = 30

    def get(self, request, model):
        model_mapping = {
            'sports': Sport,
            'business': Business,
            'latest': LatestPosts,
        }

        model_class = model_mapping.get(model)

        if model_class:
            queryset = model_class.objects.all().order_by('-pk')
            paginator = Paginator(queryset, self.items_per_page)
            posts = paginator.get_page(request.GET.get('page'))
            return render(request, self.template_name, {'posts': posts, 'modelName': str(model_class.__name__)})
        else:
            return HttpResponseNotFound(f"Category '{model}' not found")

