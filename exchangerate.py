import os
import random
import time
import uuid
import requests
from bs4 import BeautifulSoup
import threading
from datetime import datetime
import pymysql
import base64
import ddddocr
import platform

os_name = platform.system()
print(os_name)

JP_CN_table = '''CREATE TABLE `JP-CN` (
  `ID` varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `date` datetime(3) NOT NULL,
  `exchange_rate` float NOT NULL,
  `data_from` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  PRIMARY KEY (`date`) USING BTREE,
  KEY `‌index` (`ID`,`date`,`exchange_rate`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;'''

BOC_ExchangeRate_table = '''CREATE TABLE `BOC_ExchangeRate` (
  `uuid` char(36) NOT NULL,
  `currency_name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `exchange_buy_price` float DEFAULT NULL,
  `banknote_buy_price` float DEFAULT NULL,
  `exchange_sell_price` float DEFAULT NULL,
  `banknote_sell_price` float DEFAULT NULL,
  `BOC_price` float DEFAULT NULL,
  `release_time` datetime DEFAULT NULL,
  PRIMARY KEY (`uuid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;'''


def now_time():
    now = time.time()
    datetime_obj = datetime.fromtimestamp(now)
    formatted_date = datetime_obj.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    return formatted_date


class DateBase:
    def __init__(self):
        host = '172.16.1.22'
        port = 3306
        user = 'makuro'
        password = 'SRCak2244@'
        self.db = pymysql.connect(host=host, port=port, user=user, password=password)

    def insert(self, sql):
        cursor = self.db.cursor()
        cursor.execute(sql)
        self.db.commit()
        self.db.close()

    def update(self, sql):
        cursor = self.db.cursor()
        cursor.execute(sql)
        self.db.commit()
        cursor.close()
        return True

    def select(self, sql):
        cursor = self.db.cursor()
        cursor.execute(sql)
        result = cursor.fetchall()
        cursor.close()
        return True, result

    def delete(self, sql):
        try:
            cursor = self.db.cursor()
            cursor.execute(sql)
            self.db.commit()  # 提交事务，保存删除操作
            cursor.close()
        except Exception as e:
            if "timed out" in str(e):
                print("连接数据库超时", 'error')
            print(sql)
            self.db.rollback()  # 回滚事务，撤销删除操作
        finally:
            if hasattr(self, 'db') and self.db:
                self.db.close()


def get_exchanger_rete_google():
    while True:
        exchange_rate = None
        element = None
        # 目标网页URL
        url = 'https://www.google.com/finance/quote/JPY-CNY'
        # 获取网页内容
        proxy = {
            'http': 'http://172.16.1.10:10811',
            # 'http': 'http://127.0.0.1:10811',
        }
        session = requests.Session()
        session.proxies.update(proxy)

        response = session.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')

            # 查找具有特定类名的元素
            elements = soup.find_all('div', class_='YMlKec fxKbKc')

            if not elements:
                pass

            else:
                for element in elements:
                    exchange_rate = float(element.get_text())

        else:
            print(f"无法获取网页内容，状态码: {response.status_code}")

        sql = "SELECT * FROM `ExchangeRate`.`JP-CN` ORDER BY `date` DESC LIMIT 1"
        flag, data = DateBase().select(sql)
        data = float(data[0][2])
        if data == exchange_rate:
            print(f'{now_time()} - Google 未更新汇率')
            time.sleep(3600)
            continue

        sql = (f"INSERT INTO `ExchangeRate`.`JP-CN` (`ID`, `date`, `exchange_rate` , `data_from`) VALUES "
               f"('{uuid.uuid4()}', '{now_time()}' ,{exchange_rate}, 'Google');")
        DateBase().insert(sql)
        print(f"{now_time()} - Google - {element.get_text()}")
        time.sleep(3600)


def BOC_exchange_rate():
    from pathlib import Path
    ocr = ddddocr.DdddOcr()
    img_path = None
    if os_name == 'Windows':
        img_path = f'C:\\Users\\{os.getlogin()}\\AppData\\Local\\Temp\\boc_captcha.png'
        print(img_path)
    while True:
        exchange_rate = None
        captcha_jsp = 'https://srh.bankofchina.com/search/whpj/CaptchaServlet.jsp'
        response = requests.get(captcha_jsp)
        token = response.headers.get('token')
        captcha_code = response.text
        image_data = base64.b64decode(captcha_code)
        with open(img_path, 'wb') as file:
            file.write(image_data)
        with open(img_path, 'rb') as f:
            img_bytes = f.read()

        Path(img_path).unlink()
        res = ocr.classification(img_bytes)
        headers = {
            "content-type": "application/x-www-form-urlencoded",
        }
        data = {
            "pjname": "日元",  # 请求参数，传递“日元”
            "captcha": res,
            "token": token

        }
        url = 'https://srh.bankofchina.com/search/whpj/search_cn.jsp'
        response = requests.post(url, headers=headers, data=data)

        soup = BeautifulSoup(response.content, 'html.parser')
        elements = soup.find_all('div', class_='BOC_main publish')

        exchange_rate_list = []
        for element in elements:
            exchange_rate = element.get_text()
            exchange_rate = exchange_rate.replace("\r", "").replace(' ', '').replace('\t', '')
            exchange_rate_list.append(exchange_rate)

        lines = exchange_rate.split("\n")
        filtered_data = [item for item in lines if item]
        filtered_data.pop()

        filtered_data_list = []

        for i in range(len(filtered_data) // 7):
            filtered_data_list.append([
                filtered_data[0 + i * 7],
                filtered_data[1 + i * 7],
                filtered_data[2 + i * 7],
                filtered_data[3 + i * 7],
                filtered_data[4 + i * 7],
                filtered_data[5 + i * 7],
                filtered_data[6 + i * 7]
            ])
        filtered_data_list.pop(0)

        sql = f'SELECT * FROM `ExchangeRate`.`BOC_ExchangeRate` ORDER BY `release_time` DESC LIMIT 1'
        flag, data = DateBase().select(sql)
        if data:
            DB_release_time = data[0][7]
        else:
            DB_release_time = ' '
        for information in filtered_data_list:
            # print(information)
            release_time = datetime.strptime(information[6], '%Y.%m.%d%H:%M:%S')
            if release_time == DB_release_time:
                print(f'{now_time()} - BOC 未更新汇率')
                time.sleep(1800)
                break
            else:
                sql = (f"INSERT INTO `ExchangeRate`.`BOC_ExchangeRate` "
                       f"(`uuid`, `currency_name`, `exchange_buy_price`, `banknote_buy_price`, `exchange_sell_price`,"
                       f" `banknote_sell_price`, `BOC_price`, `release_time`) VALUES"
                       f" ('{uuid.uuid4()}', 'JPY', {float(information[1])}, {float(information[2])}, "
                       f"{float(information[3])}, {float(information[4])}, {float(information[5])}, '{release_time}');")
                DateBase().insert(sql)
                print(f"{now_time()} - BOC - {information}")


def robot():
    return
    while True:
        sql = "SELECT * FROM `ExchangeRate`.`JP-CN` ORDER BY `date` DESC LIMIT 1"
        flag, Google_data = DateBase().select(sql)
        Google = Google_data[0][2]

        sql = f'SELECT * FROM `ExchangeRate`.`BOC_ExchangeRate` ORDER BY `release_time` DESC LIMIT 1'
        flag, BOC_data = DateBase().select(sql)
        BOC_data = BOC_data[0]
        # text = (f'当前Google汇率  {Google} '
        #         f'当前BOC汇率：'
        #         f'发布时间: {BOC_data[7]}'
        #         f'现汇买入价: {BOC_data[2]} '
        #         f'现钞买入价: {BOC_data[3]} '
        #         f'现汇卖出价: {BOC_data[4]} '
        #         f'现钞卖出价: {BOC_data[5]} '
        #         f'中行折算价: {BOC_data[6]} ')

        text = (f'Google - {Google} '
                f'BOC - {BOC_data[4]}')

        url = f'http://172.16.1.19:3000/send_group_msg?group_id=651936926&message={text}'
        requests.get(url)
        hours = random.randint(12, 24)
        time.sleep(3600 * hours)


thread1 = threading.Thread(target=get_exchanger_rete_google)
thread2 = threading.Thread(target=robot)
thread3 = threading.Thread(target=BOC_exchange_rate)

thread1.start()
thread2.start()
thread3.start()
