import hashlib
import random
import secrets
import threading
import time
import requests
import json
import uuid
import logging
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

original_request = requests.Session.request

ua = UserAgent()


class AuthCache:
    def __init__(self):
        self.data = None
        self.expire_at = 0
        self.lock = threading.Lock()
        self.ttl = 20


_cache = AuthCache()


class PatchSign:
    def __init__(self):
        self.patched = False

    def set_patch(self, patched):
        self.patched = patched

    def is_patched(self):
        return self.patched


_patch_sign = PatchSign()


def _get_nid(user_agent):
    """
    huoqudongfangcaifude NID shouquanlingpai

    Args:
        user_agent (str): yonghudailizifuchuan竊똹ongyumonibutongdeliulanqifangwen

    Returns:
        str: fanhuihuoqudaode NID shouquanlingpai竊똱uguohuoqushibaizefanhui None

    gongnengshuoming:
        gaihanshutongguoxiangdongfangcaifudeshouquanjiekousendqingqiulaihuoqu NID lingpai竊?
        yongyuhouxudeshujufangwenshouquan?괿anshushixianlehuancunjizhilaibimianpinfanqingqiu??
    """
    now = time.time()
    # jianchahuancunshifouyouxiao竊똟imianchongfuqingqiu
    if _cache.data and now < _cache.expire_at:
        return _cache.data
    # shiyongxianchengsuoquebaobingfaanquan
    with _cache.lock:
        try:
            def generate_uuid_md5():
                """
                shengcheng UUID bingduiqijinxing MD5 haxichuli
                :return: MD5 haxizhi竊?2weishiliujinzhizifuchuan竊?
                """
                # shengcheng UUID
                unique_id = str(uuid.uuid4())
                # dui UUID jinxing MD5 haxi
                md5_hash = hashlib.md5(unique_id.encode('utf-8')).hexdigest()
                return md5_hash

            def generate_st_nvi():
                """
                shengcheng st_nvi zhidefangfa
                :return: fanhuishengchengde st_nvi zhi
                """
                HASH_LENGTH = 4  # jiequhaxizhideqianjiwei

                def generate_random_string(length=21):
                    """
                    shengchengzhidingchangdudesuijizifuchuan
                    :param length: zifuchuanchangdu竊똫orenwei 21
                    :return: suijizifuchuan
                    """
                    charset = "useandom-26T198340PX75pxJACKVERYMINDBUSHWOLF_GQZbfghjklqvwyzrict"
                    return ''.join(secrets.choice(charset) for _ in range(length))

                def sha256(input_str):
                    """
                    jisuan SHA-256 haxizhi
                    :param input_str: shuruzifuchuan
                    :return: haxizhi竊늮hiliujinzhi竊?
                    """
                    return hashlib.sha256(input_str.encode('utf-8')).hexdigest()

                random_str = generate_random_string()
                hash_prefix = sha256(random_str)[:HASH_LENGTH]
                return random_str + hash_prefix

            url = "https://anonflow2.eastmoney.com/backend/api/webreport"
            # suijixuanzepingmufenbianlv竊똺engjiaqingqiudezhenshixing
            screen_resolution = random.choice(['1920X1080', '2560X1440', '3840X2160'])
            payload = json.dumps({
                "osPlatform": "Windows",
                "sourceType": "WEB",
                "osversion": "Windows 10.0",
                "language": "zh-CN",
                "timezone": "Asia/Shanghai",
                "webDeviceInfo": {
                    "screenResolution": screen_resolution,
                    "userAgent": user_agent,
                    "canvasKey": generate_uuid_md5(),
                    "webglKey": generate_uuid_md5(),
                    "fontKey": generate_uuid_md5(),
                    "audioKey": generate_uuid_md5()
                }
            })
            headers = {
                'Cookie': f'st_nvi={generate_st_nvi()}',
                'Content-Type': 'application/json'
            }
            # zengjiachaoshi竊똣angzhiwuxiandengdai
            response = requests.request("POST", url, headers=headers, data=payload, timeout=30)
            response.raise_for_status()  # dui 4xx/5xx xiangyingpaochu HTTPError

            data = response.json()
            nid = data['data']['nid']

            _cache.data = nid
            _cache.expire_at = now + _cache.ttl
            return nid
        except requests.exceptions.RequestException as e:
            logger.warning(f"qingqiudongfangcaifushouquanjiekoushibai: {e}")
            _cache.data = None
            # gaijiekourequest_failedshi竊똣angankenengyishixiao竊똦ouxudagailvhuijixushibai竊똹inwufachenggonghuoqu竊똸iacihuijixuqingqiu竊똲hezhijiaozhangguoqishijian竊똩ebimianpinfanqingqiu
            _cache.expire_at = now + 5 * 60
            return None
        except (KeyError, json.JSONDecodeError) as e:
            logger.warning(f"jiexidongfangcaifushouquanjiekouxiangyingshibai: {e}")
            _cache.data = None
            # gaijiekourequest_failedshi竊똣angankenengyishixiao竊똦ouxudagailvhuijixushibai竊똹inwufachenggonghuoqu竊똸iacihuijixuqingqiu竊똲hezhijiaozhangguoqishijian竊똩ebimianpinfanqingqiu
            _cache.expire_at = now + 5 * 60
            return None


def eastmoney_patch():
    if _patch_sign.is_patched():
        return

    def patched_request(self, method, url, **kwargs):
        # paichufeimubiaoyuming
        is_target = any(
            d in (url or "")
            for d in [
                "fund.eastmoney.com",
                "push2.eastmoney.com",
                "push2his.eastmoney.com",
            ]
        )
        if not is_target:
            return original_request(self, method, url, **kwargs)
        # huoquyigesuijide User-Agent
        user_agent = ua.random
        # chuli Headers竊쉛uebaobupohuaiyewudaimachuanrude headers
        headers = kwargs.get("headers", {})
        headers["User-Agent"] = user_agent
        nid = _get_nid(user_agent)
        if nid:
            headers["Cookie"] = f"nid18={nid}"
        kwargs["headers"] = headers
        # suijixiumian竊똨iangdibeifengfengxian
        sleep_time = random.uniform(1, 4)
        time.sleep(sleep_time)
        return original_request(self, method, url, **kwargs)

    # quanjutihuan Session de request rukou
    requests.Session.request = patched_request
    _patch_sign.set_patch(True)

