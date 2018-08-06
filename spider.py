import json
from json import JSONDecodeError
from multiprocessing.pool import Pool
from urllib.parse import urlencode
import os
from hashlib import md5

import pymongo
from requests.exceptions import RequestException
import requests
from bs4 import BeautifulSoup
import re
from config import * #导入mongodb配置

client = pymongo.MongoClient(MONGO_URL, connect=False) #声名mongodb对象，传递url
db = client[MONGO_DB] #传递名称

#第一步
def get_page_index(offset,keyword): #将可变的参数传递过来
    data = {
        'offset': offset,
        'format': 'json',
        'keyword': keyword,
        'autoload': 'true',
        'count': 20,
        'cur_tab': 1,
        'from': 'search_tab',
    }
    url = 'https://www.toutiao.com/search_content/?' + urlencode(data)
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.text
    except RequestException:
        print('请求索引页错误')
        return None

#第四步
def parse_page_index(html):
    try:
        data = json.loads(html)
        if data and 'data' in data.keys():
            for item in data.get('data'):
                #print(item)
                yield item.get('article_url')
    except JSONDecodeError:
        pass

#第五步，拿到详情页的请求信息
def get_page_detail(url):
    headers = {
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.84 Safari/537.36'
    }
    try:
        response = requests.get(url,headers=headers)
        if response.status_code == 200:
            return response.text
    except RequestException:
        print('请求详情页错误')
        return None

#第六步
def parse_page_detail(html,url):
    soup = BeautifulSoup(html,'lxml')
    title = soup.select('title')[0].get_text()
    #print(title)
    images_pattern = re.compile('gallery: JSON\.parse\("(.*?)"\),',re.S)
    result = re.search(images_pattern,html)
    if result:
        data = json.loads(result.group(1).replace('\\',''))
        if data and 'sub_images' in data.keys():
            sub_images = data.get('sub_images')
            images = [item.get('url') for item in sub_images]
            for image in images: download_image(image)
            return {
                'title':title,
                'url':url,
                'images':images,
            }

#第七步，存储mongodb的方法
def save_to_mongo(result):
    if db[MONGO_TABLE].insert(result):
        print('存储mongodb成功', result)
        return True
    return False

#第八步
def download_image(url):
    print('正在下载：', url)
    try:
        response = requests.get(url)
        if response.status_code == 200:
           save_image(response.content)
    except RequestException:
        print('请求图片错误')
        return None

#第九步
def save_image(content):
    file_path = '{0}/{1}.{2}'.format(os.getcwd(), md5(content).hexdigest(), 'jpg')
    if not os.path.exists(file_path):
        with open(file_path, 'wb') as f:
            f.write(content)
            f.close()

#第二步
def main(offset):
    html = get_page_index(offset,KEYWORD)
    #print(html)
    for url in parse_page_index(html):
        #print(url)
        html = get_page_detail(url)
        #print(html)
        if html:
            result = parse_page_detail(html,url)
            #print(result)
            if result: save_to_mongo(result)


#第三步
if __name__ == '__main__':
    groups = [x * 20 for x in range(GROUP_START, GROUP_END + 1)]
    pool = Pool()
    pool.map(main,groups)

