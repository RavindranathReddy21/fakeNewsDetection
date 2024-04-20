import requests
import re

from transformers import pipeline
from transformers import (
    AutoTokenizer,
    AutoModelForTokenClassification
)
from clickbait import clickbait
from spellchecker import SpellChecker
from subjectivemodel import subjective
from urllib.parse import urlparse
from isnewstitle import checkNewsTitle
from bs4 import BeautifulSoup
from similarity import calculate_sentence_similarity
from right import check_similarity6


class checkTitle:
    def __init__(self, title):
        self.headline = title
        self.own_corrections = {"iam": "i'm", "im": "i'm"}
        self.corrected = title
        self.misspelled_words = []
        self.required = []
        self.contexts = []
        self.article = ""
        self.recom_link = ""
        self.most_index = 0
        self.max_similarity = 0

    def lower_case(self, text):
        text = text.lower()
        pattern = re.compile("<.*?>")
        text = pattern.sub(r"", text)
        pattern = re.compile(r"https?://\S+|www\.\S+")
        text = pattern.sub(r"", text)
        exclude = '[:\!\#\$%\&\(\)\*\+,\.\-"/\:\;<=>\?@\[\]\^_`\{\|\}\~]'
        return text.translate(str.maketrans("", "", exclude))

    def spelling_mistakes(self):
        head = self.lower_case(self.headline)
        model = AutoModelForTokenClassification.from_pretrained("dbmbz")
        tokenizer = AutoTokenizer.from_pretrained("dbmbz")
        ner_pipeline = pipeline(
            "ner", model=model, tokenizer=tokenizer, grouped_entities=True
        )
        head2 = " ".join([i.capitalize() for i in head.split()])

        ner_results = ner_pipeline(head2)
        named_entities = [
            entity["word"].lower()
            for entity in ner_results
            if entity["entity_group"] == "PER" or entity["entity_group"] == "LOC"
        ]

        misspelled_words = []
        # parser = GingerIt()
        spell = SpellChecker()
        words = []

        for token_text in head.split(" "):
            # corrected_token = parser.parse(token_text)['result'].lower()
            corrected_token = spell.correction(token_text)
            if token_text.isalpha() and token_text not in named_entities:
                if token_text in self.own_corrections:
                    words.append(self.own_corrections[token_text])
                    misspelled_words.append(token_text)
                elif token_text != corrected_token:
                    misspelled_words.append(token_text)
                    if corrected_token is None or corrected_token == "":
                        words.append(token_text)
                    else:
                        words.append(corrected_token)
                else:
                    words.append(token_text)
            else:
                words.append(token_text)

        self.corrected = " ".join(words)
        self.misspelled_words = set(misspelled_words)
        if len(misspelled_words) == 0:
            return True
        ratio = len(misspelled_words) / len(self.headline.split(" "))
        return ratio < 0.5

    def classify_clickbait(self):
        click = clickbait(self.corrected)
        return click.run() == 0

    def subjective_test(self):
        subjective_obj = subjective()
        answer = subjective_obj.send_request(self.headline)
        return answer == "objective"

    def is_newstitle(self):
        is_news = checkNewsTitle(self.headline).run()
        if is_news[0] == 0:
            return False
        return True

    def present_on_google(self):
        url = f"https://www.google.com/search?q={self.headline}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        try:
            response = requests.get(url, headers=headers)
        except:
            return False
        soup = BeautifulSoup(response.content, "html.parser")
        search_results = soup.find_all("div", class_="yuRUbf")
        search_contexts = soup.find_all(
            "div", {"class": ["VwiC3b", "yXK7lf", "lVm3ye", "r025kc", "hJNv6b", "Hdw6tb"]}
        )

        search_contexts = [
            i
            for i in search_contexts
            if str(i).find('class="VwiC3b yXK7lf lVm3ye r025kc hJNv6b Hdw6tb"') != -1
        ]
        urls = []
        print(len(search_results))
        print(len(search_contexts))
        for result, context in zip(search_results, search_contexts):
            link = result.find("a")
            url = link["href"]
            heading = result.find(re.compile("^h[1-6]$")).text
            try:
                response = requests.get(url, timeout=4)
                soup = BeautifulSoup(response.content, "html.parser")
                parsed_url = urlparse(url)
                domain_name = parsed_url.netloc
                domain_name = domain_name.replace("www.", "")
                if soup.find("title") and self.present_on_google_news_2(domain_name):
                    self.required.append(soup.find("title").text)
                    if len(context.find_all("span")) > 2:
                        self.contexts.append(context.find_all("span")[2].text)
                    elif len(context.find_all("span")) > 1:
                        self.contexts.append(context.find_all("span")[1].text)
                    else:
                        self.contexts.append(context.find_all("span")[0].text)
                    urls.append(url)
            except:
                continue

        print(len(urls))
        print(len(self.contexts))
        print(len(self.required))

        if len(self.required) < 3:
            return False
        return self.availability_on_web(urls)

    def availability_on_web(self, results):
        similar_links = []
        max_similarity = 0
        article_heading = ""
        aggregate_similarity = 0

        for result, context in zip(self.required, self.contexts):
            similarity_percentage_1 = calculate_sentence_similarity(
                self.headline, result
            )
            similarity_percentage_2 = calculate_sentence_similarity(
                self.headline, context
            )
            if similarity_percentage_1 > similarity_percentage_2:
                if similarity_percentage_1 >= max_similarity:
                    self.most_index = self.required.index(result)
                    max_similarity = similarity_percentage_1
                    article_heading = result
            else:
                if similarity_percentage_2 > max_similarity:
                    self.most_index = self.contexts.index(context)
                    max_similarity = similarity_percentage_2
                    article_heading = context
            similarity_percentage = max(
                similarity_percentage_1, similarity_percentage_2
            )
            if similarity_percentage >= 0.50:
                similar_links.append(similarity_percentage)
                aggregate_similarity += similarity_percentage

        self.article = article_heading
        if article_heading in self.required:
            self.recom_link = results[self.required.index(article_heading)]
        else:
            self.recom_link = results[self.contexts.index(article_heading)]

        if len(similar_links) < 2:
            return False

        article_heading = article_heading.replace("\n", "")
        article_heading = article_heading.lstrip()

        x1 = check_similarity6(self.headline, article_heading)

        if not x1:
            return False

        aggregate_similarity = aggregate_similarity / len(similar_links)

        self.max_similarity = aggregate_similarity

        return True

    def present_on_google_news_2(self, domain):
        print(domain)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        ggl_news_link = f"https://www.google.com/search?q={domain}&tbm=nws"
        try:
            req = requests.get(ggl_news_link, headers=headers)
            sup = BeautifulSoup(req.content, "html.parser")
            link = sup.find("a", class_="WlydOe")
            if link:
                nd_domain = urlparse(link["href"])
                domain_name = nd_domain.netloc
                domain_name = domain_name.replace("www.", "")
                print(domain, domain_name)
                if domain in domain_name:
                    return True
            return False
        except:
            return False

    def run(self):
        print(self.is_newstitle())
