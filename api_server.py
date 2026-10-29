from project_settings import setting
from flask import Flask, jsonify, request
import pymysql

app = Flask(__name__)

# === 华为云数据库连接信息 ===
DB_HOST = setting('API_DB_HOST')
DB_PORT = int(setting('API_DB_PORT'))
DB_USER = setting('API_DB_USER')
DB_PASS = setting('API_DB_PASSWORD')
DB_NAME = setting('API_DB_NAME')
TABLE = setting('API_DB_TABLE')

def get_conn():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor
    )

@app.get("/api/device/latest")
def device_latest():
    device_no = request.args.get("deviceNo", "").strip()
    if not device_no:
        return jsonify({"error": "missing deviceNo"}), 400

    sql = f"""
        SELECT id, deviceNo, eventTime, temperature, humidity, createTime
        FROM {TABLE}
        WHERE deviceNo = %s
        ORDER BY createTime DESC
        LIMIT 1
    """

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (device_no,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "no data for this device"}), 404

            # pymysql 可能把 Decimal/Datetime 带出来，这里统一转成可 JSON 化
            out = {
                "id": row["id"],
                "deviceNo": row["deviceNo"],
                "eventTime": row["eventTime"],
                "temperature": float(row["temperature"]) if row["temperature"] is not None else None,
                "humidity": float(row["humidity"]) if row["humidity"] is not None else None,
                "createTime": str(row["createTime"]) if row["createTime"] is not None else None,
            }
            return jsonify(out)
    finally:
        conn.close()

@app.get("/api/overview")
def overview():
    # 只有一个设备：你可以固定 deviceTotal=1
    # online/offline/alarm 你如果没有“在线状态表”，先按“最近N分钟有数据=在线”做个简单规则
    device_no = request.args.get("deviceNo", "Cjy9874123").strip()
    minutes = int(request.args.get("minutes", "10"))

    sql = f"""
        SELECT COUNT(*) AS cnt
        FROM {TABLE}
        WHERE deviceNo=%s AND createTime >= (NOW() - INTERVAL %s MINUTE)
    """

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (device_no, minutes))
            cnt = cur.fetchone()["cnt"]

        online = 1 if cnt > 0 else 0
        offline = 1 - online
        # alarm 没有字段就先 0；后面你接 alarm_log 表再做
        return jsonify({
            "deviceTotal": 1,
            "online": online,
            "offline": offline,
            "alarm": 0
        })
    finally:
        conn.close()

if __name__ == "__main__":
    # 监听 0.0.0.0 方便局域网/前端访问；端口你随便
    app.run(host="0.0.0.0", port=5000, debug=True)
