import base64
import glob
import os
from io import BytesIO

import cv2
import torch
import numpy as np
from PIL import Image
from flask import Flask, render_template, request, Response, session, flash, redirect, url_for
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from httplib2 import Http
from oauth2client import file, client, tools
import pymysql

HOST = '0.0.0.0'

app = Flask(__name__)
# session, flash 사용 시 필요한 secret_key 설정 임의의 값을 넣으면 됨
app.secret_key = 'aabbccdd1234!'
# QR 인식 후 회원 정보를 저장 할 전역 변수
memInfo = ""



# 구글 인증. 최초 실행시 storage.json에 저장.
# 1시간 지나면 만료되기 때문에 이 함수를 실행후 구글 드라이브 API 사용권한획득과 업로드가 이루어짐.
def google_access():
    scopes = 'https://www.googleapis.com/auth/drive.file'
    store = file.Storage('storage.json')
    creds = store.get()

    try:
        import argparse
        flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
    except ImportError:
        flags = None

    if not creds or creds.invalid:
        print('make new cred')
        flow = client.flow_from_clientsecrets('client_secret.json', scopes)
        creds = tools.run_flow(flow, store, flags) if flags else tools.run_flow(flow, store)


# okjaejoon 구글 드라이브계정 Blisgo Collected image 폴더
blisgo_dir_id = '1PPVS5WKJq3x2paa4cA7hoiDV4844dImH'
cardboard_dir_id = '11HZzVYWDTb19T4k-2A5tdfdXN-kPxCNf'
carton_dir_id = '1jsRg4Rf5QBUYmUyu_ADy8l817tFHmFz8'
glass_dir_id = '1Vi2gXVdnVMugbgSutARxmvuMax54uOPj'
metal_dir_id = '1yfORAEYcgTQoobvnZnBFBPuLEt_2o8Zv'
plastic_dir_id = '13wGc1nzwD02s9Ac8Pb2hSIy4lxpng6vJ'
etc_dir_id = '18TP9tdJCKYYJTgO8rusWEUV6tEnyfKTK'
# 이미지가 일시적으로 저장되는 폴더
images_dir_id = '126FqxSkulMHdgSkOS347uSLek1cInpK1'

# yolov5분석후 추출되는 숫자를 해당 문자열로 변경
def label_name(num):
    return {
        0: "cardboard",
        1: "cartons",
        2: "glass",
        3: "metal",
        4: "plastic",
        5: "None"
    }[num]



@app.route('/')  # 접속하는 url
def index():
    return render_template('index.html')


@app.route('/401')
def Protected401():
    return render_template('401.html')


@app.route('/404')
def error404():
    return render_template('404.html')


@app.route('/analyze')
def analyze():
    return render_template('analyze.html')


@app.route('/classification')
def classification():
    if 'mem_no' in session:
        memNo = session['mem_no']
        print(memNo)
    return render_template('classification.html')


@app.route('/login-method')
def loginmethod():
    return render_template('login-method.html')


@app.route('/login')
def login():
    return render_template('login.html')


@app.route('/pending')
def pending():
    return render_template('pending.html')


# base64형태의 이미지와 이미지 저장공간 전달
@app.route('/reportPOST', methods=["POST"])
def reportPOST():
    if request.method == "POST":
        draw = request.form['textArea']
        non_identify = request.form['textArea2']
    return render_template('report.html', draw=draw, img=non_identify)


@app.route('/report')
def report():
    return render_template('report.html')

@app.route('/success')
def success():
    return render_template('success.html')

@app.route('/google', methods=["POST"])
def google():
    folName = request.form.get('sorting-2')
    img = request.form['textArea2'] # ex) 2021_8_8_15_29_15 이런식으로 이미지가 있다.
    google_access()
    # 구글 드라이브 API 사용 권한획득 후 인증 정보 저장
    store = file.Storage('storage.json')
    creds = store.get()
    drive = build('drive', 'v3', http=creds.authorize(Http()))

    uploadfile = "./images/" + str(img) + ".jpg"
    # 파일 이름에 따라 클라우드 폴더에 분류 저장
    fname = uploadfile
    if folName == 'cardboard':  # 종이박스
        folder_id = cardboard_dir_id
    elif folName == 'carton':  # 우유곽
        folder_id = carton_dir_id
    elif folName == 'glass':  # 유리
        folder_id = glass_dir_id
    elif folName == 'metal':  # 철
        folder_id = metal_dir_id
    elif folName == 'plastic':  # 플라스틱
        folder_id = plastic_dir_id
    else:
        folder_id = etc_dir_id
    # 업로드 대상이 이미지이기 때문에 미디어 형태로 변환
    media = MediaFileUpload(fname, format(fname))

    # 업로드 했을때 구글 드라이브에 표기될 정보(metadata)를 설정
    metadata = {
        'name': str(folName) + fname,  # 파일 이름
        'parents': [folder_id],  # 파일 저장 경로
        'mimeType': 'image/jpeg'  # 파일 확장자. MIME TYPE 참고해서 작성
    }

    # 이미지 업로드
    res = drive.files().create(body=metadata, media_body=fname).execute()
    if res:
        print('upload %s' % fname)

    return render_template('index.html')


# login.html <img>태그 부분에 연결된 method로 gen_frames()함수를 호출함
#@app.route('/video_feed')
# def video_feed():
#     """Video streaming route. Put this in the src attribute of an img tag."""
#     return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


# QR 인식을 토대로 DB 이용 로그인 실행 부분
@app.route("/qrlogin", methods=["POST"])
def qrlogin():
    if request.method == "POST":
        global memInfo
        draw = request.form['textArea']
        # ,이후가 우리가 쓸 의미 있는 base64값
        starter = draw.find(',')
        image_data = draw[starter + 1:]
        image_data = bytes(image_data, encoding="ascii")
        im = base64.b64decode(image_data)
        npimg = np.frombuffer(im, dtype=np.uint8)
        qrimg = cv2.imdecode(npimg, 1)
        qrCodeDetector = cv2.QRCodeDetector()
        decodedText, points, _ = qrCodeDetector.detectAndDecode(qrimg)

        if points is not None:
            # QR Code detected handling code
            print(decodedText)
        else:
            print("QR code not detected")

        memQr = decodedText.split('&')
        memEmail = memQr[0]
        memPass = memQr[1]
        print(memEmail)
        print(memPass)
        db = pymysql.connect(
            host='ckshdphy86qnz0bj.cbetxkdyhwsb.us-east-1.rds.amazonaws.com',
            port=3306,
            user='ryf4ncny3acgdegg',
            passwd='bmwv6aftls3448xj',
            db='lf8f4vd04ehom5q7',
            charset='utf8'
        )
        cursor = db.cursor(pymysql.cursors.DictCursor)
        sql = 'select * from mem_db where email=\'' + memEmail + '\' and pass=\'' + memPass + '\''
    # DB 내에 회원 정보가 없을 경우
    if cursor.execute(sql) == 0:
        # 웹 페이지에 알람 표시
        flash("없는 회원입니다.")
        # 다시 QR 인식 화면으로 보냄
        return redirect(url_for("login"))
    # 회원 정보가 맞을 경우
    else:
        rows = cursor.fetchall()
        print(rows)
        # session을 이용해서 회원 ID 정보를 저장 다른 함수에서 session['userId']를 이용해서 회원 아이디 정보 사용 가능 -> classfication 함수쪽에 사용 예 있음
        flash(rows[0]['nickname'] + "님 환영합니다. 쓰레기를 카메라에 보여주세요.")
        session['mem_no'] = rows[0]['mem_no']
    return redirect(url_for("classification"))


@app.route('/predict', methods=["POST"])
def predict():
    if request.method == "POST":
        draw = request.form['textArea']
        # 그 전에 찍은 남아있는 이미지 모두 제거
        # [os.remove(f) for f in glob.glob("./images/*.jpg")]

        # amd <- path  Nvidia path_or_model
        model = torch.hub.load('ultralytics/yolov5', 'custom', path='model/best.pt')
        # model = torch.hub.load('ultralytics/yolov5', 'custom', path_or_model='./model/best.pt')

        # base64형태의 이미지정보를 html에서 가져옴
        img_name = request.form['textArea2']
        # 새롭게 저장될 이미지의 경로와 파일명을 결정
        img = "./images/" + str(img_name) + ".jpg"

        # ,이후가 우리가 쓸 의미 있는 base64값
        starter = draw.find(',')
        image_data = draw[starter + 1:]
        image_data = bytes(image_data, encoding="ascii")
        im = Image.open(BytesIO(base64.b64decode(image_data)))
        # 이미지 저장시 기본이 RGBA 인데 jpg는 A가 없습니다. 그래서 RGB로 convert
        im = im.convert('RGB')
        # save(경로) 경로 안에 파일을 저장합니다.
        # im.save("./images/" + str(img_name) + ".jpg")
        # 이미지를 저장하고 yolov5 분석 시작
        # Image.open(img)
        output = model(im)
        label1 = output.xyxy[0].numpy()  # 분석후 출력되는 배열을 일차원 배열로 변경
        print(label1[0])
        # 인식되는 배열이 있다면 analyze.html로 이미지와 결과값을 전달
        if label1.all():
            result = label1[0]
            result1 = label_name(result[-1])
            confidence = int(result[-2] * 100)
            return render_template('analyze.html', draw=draw, result=result1, img=img_name, confidence=confidence)
        # 인식되는 배열이 없다는 것에 대한 예외처리
        else:
            result1 = label_name(5)

            return render_template('analyze.html', draw=draw, result=result1, img=img_name)



if __name__ == '__main__':
    app.debug = True
    port = int(os.environ.get("PORT", 5000))
    app.run(host='localhost', port=port, debug=True)
