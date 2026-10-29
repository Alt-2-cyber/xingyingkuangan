# coding: utf-8

from project_settings import setting
import threading
import time
from datetime import datetime

import pymysql
import requests
from flask import Flask, jsonify, request
from datetime import datetime, timedelta, timezone
Time = 15
DOMAIN_NAME = setting('IOTDA_DOMAIN_NAME')
USERNAME = setting('IOTDA_USERNAME')
PASSWORD = setting('IOTDA_PASSWORD')

# 你的项目 ID 和设备 ID
PROJECT_ID = setting('IOTDA_PROJECT_ID')
DEVICE_ID = setting('IOTDA_DEVICE_ID')

# IoTDA 应用侧接入地址（确保与可用的地址一致）
IOTDA_APP_HOST = setting('IOTDA_APP_HOST')

# MySQL 连接信息
MYSQL_HOST = setting('MYSQL_HOST')
MYSQL_PORT = int(setting('MYSQL_PORT'))
MYSQL_USER = setting('MYSQL_USER')
MYSQL_PASSWORD = setting('MYSQL_PASSWORD')
MYSQL_DB = setting('MYSQL_DATABASE')
MYSQL_TABLE = setting('MYSQL_TABLE')

IAM_URL = "https://iam.myhuaweicloud.com/v3/auth/tokens"

app = Flask(__name__)


def get_db_connection():
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        charset="utf8mb4",
        autocommit=True,
    )


def get_token_domain_scope():
    headers = {
        "Content-Type": "application/json",
        "Accept": "*/*",
    }
    payload = {
        "auth": {
            "identity": {
                "methods": ["password"],
                "password": {
                    "user": {
                        "domain": {"name": DOMAIN_NAME},
                        "name": USERNAME,
                        "password": PASSWORD,
                    }
                },
            },
            # 与你提供的参考代码一致：domain scope
            "scope": {"domain": {"name": DOMAIN_NAME}},
        }
    }

    resp = requests.post(IAM_URL, headers=headers, json=payload, timeout=30)
    print("Token Status:", resp.status_code)

    if resp.status_code != 201:
        raise RuntimeError(f"获取 Token 失败: {resp.status_code} {resp.text}")

    token = resp.headers.get("X-Subject-Token")
    if not token:
        raise RuntimeError("响应头缺少 X-Subject-Token")

    return token


def fetch_shadow(token):
    url = (
        f"https://{IOTDA_APP_HOST}/v5/iot/"
        f"{PROJECT_ID}/devices/{DEVICE_ID}/shadow"
    )
    headers = {"X-Auth-Token": token}
    resp = requests.get(url, headers=headers, timeout=30)
    return resp


def parse_shadow(json_data):
    # 预期格式：{"device_id":..., "shadow":[{...}]}
    device_id = json_data.get("device_id")
    shadow_list = json_data.get("shadow") or []
    if not shadow_list:
        return None

    shadow = shadow_list[0]
    service_id = shadow.get("service_id")
    reported = shadow.get("reported") or {}
    properties = reported.get("properties") or {}

    temperature = properties.get("temperature")
    humidity = properties.get("humidity")

    event_time_raw = reported.get("event_time")
    event_time = None
    if event_time_raw:
        try:
            # 确保导入了 timezone 和 timedelta
            utc_time = datetime.strptime(event_time_raw, "%Y%m%dT%H%M%SZ")
            # 替换为UTC时区
            utc_time = utc_time.replace(tzinfo=timezone.utc)
            # 转换为北京时间（UTC+8）
            beijing_time = utc_time.astimezone(timezone(timedelta(hours=8)))
            # 去掉时区信息，保持datetime对象
            event_time = beijing_time.replace(tzinfo=None)
            print(f"成功转换时间: {event_time_raw} -> {event_time}")  # 添加调试信息
        except Exception as e:
            print(f"时间解析错误: {e}, 原始时间: {event_time_raw}")  # 添加调试信息
            event_time = None

    return {
        "device_id": device_id,
        "service_id": service_id,
        "temperature": float(temperature) if temperature is not None else None,
        "humidity": float(humidity) if humidity is not None else None,
        "event_time": event_time,
    }


def insert_shadow_row(conn, row):
    sql = (
        f"INSERT INTO {MYSQL_TABLE} "
        "(device_id, service_id, temperature, humidity, event_time) "
        "VALUES (%s, %s, %s, %s, %s)"
    )
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (
                row["device_id"],
                row["service_id"],
                row["temperature"],
                row["humidity"],
                row["event_time"],
            ),
        )


def poll_loop():
    conn = None
    token = None
    

    while True:
        try:
            if conn is None or not conn.open:
                conn = get_db_connection()

            if token is None:
                token = get_token_domain_scope()

            resp = fetch_shadow(token)

            # token 可能过期，401/403 时重新获取
            if resp.status_code in (401, 403):
                print("Token 过期或无权限，重新获取...")
                token = get_token_domain_scope()
                resp = fetch_shadow(token)

            if resp.status_code != 200:
                print("获取影子失败:", resp.status_code, resp.text)
            else:
                data = resp.json()
                row = parse_shadow(data)
                if row:
                    insert_shadow_row(conn, row)
                    print("已写入数据库:", row)
                else:
                    print("影子数据为空")
        except Exception as e:
            print("运行异常:", e)
            time.sleep(Time)
        else:
            time.sleep(Time)


@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


def _fetch_latest_row(device_no):
    sql_exact = (
        f"SELECT device_id, service_id, temperature, humidity, event_time, ingested_at "
        f"FROM {MYSQL_TABLE} WHERE device_id=%s ORDER BY id DESC LIMIT 1"
    )
    sql_like = (
        f"SELECT device_id, service_id, temperature, humidity, event_time, ingested_at "
        f"FROM {MYSQL_TABLE} WHERE device_id LIKE %s ORDER BY id DESC LIMIT 1"
    )

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(sql_exact, (device_no,))
            row = cur.fetchone()
            if row:
                return row
            cur.execute(sql_like, (f"{device_no}%",))
            row = cur.fetchone()
            if row:
                return row
            cur.execute(
                f"SELECT device_id, service_id, temperature, humidity, event_time, ingested_at "
                f"FROM {MYSQL_TABLE} ORDER BY id DESC LIMIT 1"
            )
            return cur.fetchone()
    finally:
        if conn is not None:
            conn.close()


@app.route("/api/device/latest", methods=["GET"])
def api_device_latest():
    device_no = request.args.get("deviceNo") or DEVICE_ID
    row = _fetch_latest_row(device_no)

    if not row:
        return jsonify(
            {
                "deviceNo": device_no,
                "temperature": None,
                "humidity": None,
                "createTime": None,
            }
        )

    device_id, service_id, temperature, humidity, event_time, ingested_at = row
    if event_time:
        create_time = event_time.strftime("%Y-%m-%d %H:%M:%S")
    elif ingested_at:
        # ingested_at 为数据库本地时间（通常已是北京时间）
        create_time = ingested_at.strftime("%Y-%m-%d %H:%M:%S")
    else:
        create_time = None

    return jsonify(
        {
            "deviceNo": device_id,
            "serviceId": service_id,
            "temperature": float(temperature) if temperature is not None else None,
            "humidity": float(humidity) if humidity is not None else None,
            "createTime": create_time,
        }
    )


@app.route("/api/overview", methods=["GET"])
def api_overview():
    # 页面只需要 online/offline/alarm 这些字段
    return jsonify({"online": 1, "offline": 1, "alarm": 0})


def main():
    t = threading.Thread(target=poll_loop, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()