from typing import Any, Callable, List, Dict
from collections import Counter
from datetime import date
from agentic.models import CLAUDE, GPT_4O_MINI, GPT_4O

#from agentic.tools.scaleserp_browser import ScaleSerpBrowserTool
from agentic.tools.text_to_speech_tool import TextToSpeechTool
#from .registry import tool_registry, Dependency, ConfigRequirement

import asyncio
import pandas as pd
#from .scaleserp_browser import ScaleSerpBrowserTool
from .base import BaseAgenticTool

import os
import requests
from bs4 import BeautifulSoup
import openai
"""
@tool_registry.register(
    name="ArticleScraperTool",
    description="Scrape online news articles and summarize"
)
"""

class ArticleScraperTool(BaseAgenticTool):
    def __init__(self):
        super().__init__()

    def get_tools(self) -> list[Callable]:
        return [
            self.download_and_write_article,
            self.gather_urls,
            self.summarize,
            self.news_scrape_and_download,
            self.create_podcast_from_text
        ]
    

    def download_and_write_article(
        self,
        download_url:str,
        save_file: str,
        is_summarize: bool = True,
        sum_wc: int = 500
    ):
        r = requests.get(download_url)
        soup = BeautifulSoup(r.text, 'html.parser')
        content = ""
        success = False
        with open(save_file, "a") as f:
            for title in soup.find_all('title'):
                if len(title.get_text().split()) > 3:
                    ttext = title.get_text()
            for data in soup.find_all("p"):
                content += data.get_text() + '\n'
            if len(content) > 3000:
                if is_summarize:
                    f.write(self.summarize(article=content, wordcount=sum_wc, title=ttext))   
                else:
                    f.write("\n\n"+ ttext + "\n")
                    f.write(content) 
                success = True
        return success
    

    def summarize(
        self,
        article: str,
        wordcount: int,
        title: str, 
        model="gpt-4o"
    ):
        client = openai.OpenAI()
        prompt = "Please summarize the following article titled " + title+ " in detail in " + str(wordcount) + " words in the style of a on-air news reporter. Include a introduction/transition sentence in the beginning: \n"
        prompt += article
        messages = [{"role": "user", "content": prompt}]
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
        )
        res = response.choices[0].message.content
        return res

## PODCAST SPECIFIC FUNCTIONS
    def gather_urls(
        self,
        site_url: str
    ):
        r = requests.get(site_url)
        urls = set()
        soup = BeautifulSoup(r.text, 'html.parser')
        for link in soup.find_all("a"):
            href = link.get("href")
            if site_url in href: #validates news link
                urls.add(href)
        return urls    
    
    def news_scrape_and_download(
        self,
        news_site: str,
        save_file: str,
        num_articles: int = 5,
        is_summarize: bool = True,
        sum_wc: int = 500
    ):
        with open(save_file, "w") as f:
            f.write("")
        urls = list(self.gather_urls(news_site))
        count = 0
        while count < num_articles and len(urls) > 0:
            curl = urls.pop(0)
            success = self.download_and_write_article(curl, save_file, True)
            if success:
                count += 1
    
    def create_podcast_from_text(
        self,
        save_file: str
    ):
        tts = TextToSpeechTool()
        res = tts.generate_speech_file_from_text(voice="nova", input_file_name=save_file)
        return(res)

# a = 'https://www.nbcnews.com'
# b ='/Users/annie/supercog/agentic/myagents/agents/article_scraper_transcript.txt'
# c=3
# d=True
# e=350
# ast = ArticleScraperTool()
# ast.news_scrape_and_download(news_site=a, save_file=b, num_articles=c, is_summarize=d, sum_wc=e)

"""


##VARIABLES
#news_root = "https://www.nbcnews.com"
#news_suffix = ["tech", "news", "us-news", "world", "science","business", "politics", "sports", "investigations", "health", "media", "pop-culture"]
cur_dir = os.path.dirname(os.getcwd())
default_file_path = cur_dir + "/article_scraper_transcript.txt"
##DELETE

def download_and_write_article(download_url, save_file=default_file_path, summarize=True, sum_wc=500):
    r = requests.get(download_url)
    soup = BeautifulSoup(r.text, 'html.parser')
    content = ""
    success = False
    with open(save_file, "a") as f:
        for title in soup.find_all('title'):
            if len(title.get_text().split()) > 3:
                ttext = title.get_text()
        for data in soup.find_all("p"):
            content += data.get_text() + '\n'
        if len(content) > 3000:
            f.write("\n\n"+ ttext + "\n")
            if summarize:
                f.write(summarize(content))    
            f.write(summarize(content))
            success = True
        #else:
            #print("less than 3000")
            #print(url)
    return success

def summarize(article, wordcount=500, model="gpt-4o"):
    client = openai.OpenAI()
    prompt = "Please summarize the following text in detail in " + str(wordcount) + " words in the style of a news reporter: \n"
    prompt += article
    messages = [{"role": "user", "content": prompt}]
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
    )
    res = response.choices[0].message.content
    return res

def gather_urls(site_url):
    r = requests.get(site_url)
    #print(r.status_code)
    urls = set()
    soup = BeautifulSoup(r.text, 'html.parser')
    for link in soup.find_all("a"):
        href = link.get("href")
        if site_url in href:
            urls.add(href)
    print("Gathered URLs")
    return urls

def news_segemnt_workflow(news_site, save_file=default_file_path, num_articles=5, is_summarize=True, sum_wc=500):
    with open(save_file, "w") as f:
        f.write("")
    urls = list(gather_urls(news_site))
    count = 0
    #print(urls)
    while count < num_articles and len(urls) > 0:
        print(count)
        curl = urls.pop(0)
        success = download_and_write_article(curl, save_file, True)
        if success:
            count += 1

def podcast_segment(input_file_name=default_file_path):
    tts = TextToSpeechTool()
    res = tts.generate_speech_file_from_text(voice="nova", input_file_name=file_path)
    print(res)
    return(res)


#gather_urls(news_site)

#url1 = "https://www.nbcnews.com/news/us-news/weekend-rundown-march-9-rcna195502"
#url = "https://www.nbcnews.com/news/world/mark-carney-ex-central-banker-become-canadas-prime-minister-rcna195560"
#file_from_url(url1)
#workflow()
#workflow()
#podcast_segment()

#populate()
"""