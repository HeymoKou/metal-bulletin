"""AWS Lambda PPS connectivity test — stdlib only, no deps.

Deploy:
  zip -j pps_test.zip lambda_pps_test.py
  aws lambda create-function \
    --function-name pps-test \
    --runtime python3.13 \
    --role arn:aws:iam::<ACCT>:role/lambda-basic \
    --handler lambda_pps_test.handler \
    --region ap-northeast-2 \
    --zip-file fileb://pps_test.zip \
    --timeout 30

Invoke:
  aws lambda invoke --function-name pps-test --region ap-northeast-2 out.json
  cat out.json

Cleanup:
  aws lambda delete-function --function-name pps-test --region ap-northeast-2
"""
import json
import socket
import ssl
import urllib.request
from urllib.error import HTTPError, URLError

URL = "https://www.pps.go.kr/bichuk/bbs/list.do?key=00826"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _public_ip() -> str:
    try:
        with urllib.request.urlopen("https://api.ipify.org", timeout=5) as r:
            return r.read().decode().strip()
    except Exception as e:
        return f"err:{e}"


def handler(event, context):
    result = {
        "url": URL,
        "public_ip": _public_ip(),
    }
    req = urllib.request.Request(URL, headers={
        "User-Agent": UA,
        "Accept-Language": "ko-KR,ko;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read(2048).decode("utf-8", "replace")
            result["status"] = resp.status
            result["len"] = len(body)
            result["snippet"] = body[:300]
            result["has_target"] = "주간 경제" in body or "주간희소금속" in body
    except HTTPError as e:
        result["http_error"] = f"{e.code} {e.reason}"
    except URLError as e:
        result["url_error"] = str(e.reason)
    except (socket.timeout, ssl.SSLError, ConnectionResetError, OSError) as e:
        result["net_error"] = f"{type(e).__name__}: {e}"
    return result


if __name__ == "__main__":
    print(json.dumps(handler(None, None), ensure_ascii=False, indent=2))
