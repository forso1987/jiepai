# -*- coding:utf-8 -*-
import os
from json.decoder import JSONDecodeError
from urllib.parse import urlencode
from requests.exceptions import RequestException
import requests
import pymongo
import json
from bs4 import BeautifulSoup
import re
from config import *
from hashlib import md5
from multiprocessing import Pool

client = pymongo.MongoClient(MONGO_URL, connect=False)
db = client[MONGO_DB]

def get_page_index(offset,keyword):
    data = {
        'offset': offset,
        'format': 'json',
        'keyword': keyword,
        'autoload': 'true',
        'count': '20',
        'cur_tab': '3'
    }
    url= 'https://www.toutiao.com/search_content/?' + urlencode(data)
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.text
        return None
    except RequestException:
        print('请求索引页出错')
        return None

def parse_page_index(html):
    try:
        data = json.loads(html)
        if data and 'data' in data.keys():
            for item in data.get('data'):
                yield item.get('article_url')
    except JSONDecodeError:
        pass

def get_page_detail(url):

    try:
        headers = {'user-agent':'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 UBrowser/6.2.3964.2 Safari/537.36'}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.text
        return None
    except RequestException:
        print('请求索引页出错',url)
        return None

def parse_page_detail(html,url):
    pattern = re.compile('BASE_DATA.galleryInfo.*?title:(.*?)isOriginal:.*?gallery:(.*?),\n', re.S)
    items = re.findall(pattern, html)
    for item in items:
        title = item[0].strip()[1:-2]
        result = item[1].strip()[12:-2]
    result = re.sub(r'\\','',result)
    data = json.loads(result)
    if data and 'sub_images' in data.keys():
        sub_images = data.get('sub_images')
        images = [img.get('url') for img in sub_images]
        for image in images: download_image(image)
        return{
            'title':title,
            'url':url,
            'images':images
        }

def save_to_mongo(result):
    if db[MONGO_TABLE].insert(result):
        print('存储到MongoDB成功', result)
        return True
    return False

def download_image(url):
    print('正在下载',url)
    try:
        response = requests.get(url)
        if response.status_code == 200:
            save_image(response.content)
        return None
    except RequestException:
        print('请求图片出错', url)
        return None

def save_image(content):
    file_path = '{0}/{1}.{2}'.format(os.getcwd(), md5(content).hexdigest(), 'jpg')
    if not os.path.exists(file_path):
        with open(file_path, 'wb') as f:
            f.write(content)
            f.close()
def main(offset):
    html = get_page_index(offset,KEYWORD)
    for url in parse_page_index(html):
        html = get_page_detail(url)
        parse_page_detail(html,url)
        if html:
            result = parse_page_detail(html,url)
            if result: save_to_mongo(result)

if __name__ == "__main__":
    groups = [x*20 for x in range(GROUP_START,GROUP_END+1)]
    pool = Pool()
    pool.map(main, groups)
