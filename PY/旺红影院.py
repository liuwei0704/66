# coding=utf-8
"""
旺红影视 — TVBox / FongMi T3(type=3) 爬虫源
站点：https://www.wanghonghulan.com  （MacCMS 系标准 HTML 影视站）

要点
- HTTP 会 302 跳 HTTPS，全程 https 直连。
- 首页/分类/详情页无需任何 cookie，直接可取（已实测 200）。
- 分类页：/movtype/{tid}/{pg}.html；列表卡片在 li_img / li_text 结构内，
  顶部热搜导航 anchor 不在 li_img 内，天然跳过。
- 详情页：/movdetail/{id}.html；多线路在 span#line-N(线路名) + dd.line-N(剧集) 内，
  剧集 anchor 的 href 即 /movplay/{id}/{源}/{集}.html，直接取用无需自行拼接。
- 播放解析链（已实测打通）：
    1) GET movplay 页 → iframe src = https://ttss.langfeng888.com/d5xc/player.html?v={HEX}
    2) 从 player.html 取 proxy 接口基址（根路径 /proxy/），GET {origin}/proxy/{HEX}
       → JSON {"code":200,"url":"<直链>"}
    3) 直链多为 douyinvod mp4（206 可达，禁带 Referer，带 Referer 反而 403）。
  playerContent 回 parse:0 直链，header 只带 UA。
- 搜索有人机验证：直连 /search 会 302 到 /human-check。
  预热：GET /human-check?return=... 取 challenge → POST /human-check/verify
  → 拿 maccms_human_permit cookie（3 小时）→ 带 cookie 请求 search。
- 契约：返回原生 dict/list；vod_play_from / vod_play_url 以 $$$ 严格对齐；
  homeContent 与 __init__ 零网络、分类静态硬编码。
"""
import re
import time
import base64
import json as _json
import html as _html
from urllib.parse import quote, urlparse, parse_qs

try:
    from base.spider import Spider as BaseSpider
except Exception:  # pragma: no cover
    class BaseSpider(object):
        def fetch(self, *a, **k):
            return None

        def post(self, *a, **k):
            return None


UA = ("Mozilla/5.0 (Linux; Android 14; 22127RK46C/Pixel5) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

MAIN = "https://www.wanghonghulan.com"

# ---- 主分类（零网络，静态硬编码）----
MAIN_CATS = [
    ("A2SQSSe417LaA", "电影"),
    ("A3t4CRt0cYsop", "连续剧"),
    ("A0d2hF43NnSRb", "综艺"),
    ("A23gREJ3qWKE1", "动漫"),
    ("A4gYEuZ3j7vZk", "短剧"),
]

# ---- 子分类作为「类型」筛选组（本身是独立 movtype id，选中即替换请求 tid）----
SUB_MOVIE = [
    ("A0EIg0j4IHPj6", "悬疑片"), ("A1ewPzy1EHvOC", "动作片"),
    ("A35a9zD3SPZhm", "爱情片"), ("A4WDtyS2xv5ju", "科幻片"),
    ("A1GCOld1FGQvk", "恐怖片"), ("A2gq8ks0CHj5L", "喜剧片"),
    ("A47Tsk70X1CWn", "剧情片"), ("A2cknOl4b6SKH", "动画片"),
    ("A43OXO03uIFNa", "邵氏片"),
]
SUB_SERIES = [
    ("A0rSNXI4IyvUU", "大陆剧"), ("A2I67WX04400e", "港剧"),
    ("A3ijrVm1hosFd", "台剧"), ("A1ar4dr4fBoY0", "美剧"),
    ("A2E0mAQ1ibhUc", "泰剧"), ("A0nN2BB1tRiJ4", "日剧"),
    ("A3eeW9f1o0bJ6", "韩剧"),
]


class Spider(BaseSpider):

    # ===================== 生命周期 =====================
    def init(self, extend=""):
        # 零网络：仅准备请求头
        self.headers = {
            "User-Agent": UA,
            "Accept": ("text/html,application/xhtml+xml,application/xml;"
                       "q=0.9,image/avif,image/webp,*/*;q=0.8"),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": MAIN + "/",
        }
        self._permit = None
        return self

    def getName(self):
        return "旺红影视"

    def isVideoFormat(self, url):
        url = url or ""
        return any(e in url for e in (".m3u8", ".mp4", ".ts", ".flv", ".mkv"))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    # ===================== 网络 =====================
    def _req(self, url, headers=None, cookies=None, data=None,
             is_post=False, allow_redirects=True):
        """统一取文本。self.fetch/post 优先（smoke 与真机均可），失败回空串。"""
        hd = dict(getattr(self, "headers", {"User-Agent": UA}))
        if headers:
            hd.update(headers)
        try:
            if is_post:
                r = self.post(url, data=data, headers=hd, cookies=cookies,
                              timeout=20, allow_redirects=allow_redirects)
            else:
                r = self.fetch(url, headers=hd, cookies=cookies,
                               timeout=20, allow_redirects=allow_redirects)
            if not r:
                return ""
            return r.text or ""
        except Exception:
            return ""

    # ===================== 解析助手 =====================
    @staticmethod
    def _parse_extend(extend):
        d = {}
        if isinstance(extend, dict):
            return {str(k): str(v) for k, v in extend.items()}
        if isinstance(extend, str):
            s = extend.strip().strip("{}")
            for seg in re.split(r"[,&]", s):
                if "=" in seg:
                    k, v = seg.split("=", 1)
                    d[k.strip()] = v.strip()
        return d

    @staticmethod
    def _clean(s):
        return re.sub(r"<[^>]+>", "", _html.unescape(s or "")).strip()

    def _parse_list(self, h):
        """通用列表卡片 → vod dict 列表。按 li_img 块切分，天然跳过顶部导航。"""
        out, seen = [], set()
        for block in re.split(r'<div class="li_img">', h or "")[1:]:
            mid = re.search(
                r'href="/movdetail/([^."]+)\.html"[^>]*>\s*<img[^>]*\bsrc="([^"]+)"',
                block)
            if not mid:
                continue
            vid, pic = mid.group(1), mid.group(2)
            if not vid or vid in seen:
                continue
            seen.add(vid)
            mr = re.search(r'class="rgba1"[^>]*>([^<]*)<', block)
            remark = self._clean(mr.group(1)) if mr else ""
            mt = re.search(r'class="name"[^>]*>\s*<a[^>]*>([^<]+)</a>', block)
            if not mt:
                mt = re.search(r'class="alink"[^>]*title="([^"]+)"', block)
            title = self._clean(mt.group(1)) if mt else vid
            ma = re.search(r'class="actor"[^>]*>([^<]*)<', block)
            actor = self._clean(ma.group(1)) if ma else ""
            out.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark or actor,
            })
        return out

    # ===================== 首页（零网络）=====================
    def homeContent(self, filter):
        cls = [{"type_id": tid, "type_name": name} for tid, name in MAIN_CATS]

        def _group(sub):
            vals = [{"n": "全部", "v": ""}]
            vals += [{"n": n, "v": t} for t, n in sub]
            return [{"key": "类型", "name": "类型", "value": vals}]

        filters = {
            "A2SQSSe417LaA": _group(SUB_MOVIE),
            "A3t4CRt0cYsop": _group(SUB_SERIES),
        }
        return {"class": cls, "filters": filters}

    def getHomeContent(self, filter=True):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            h = self._req(MAIN + "/")
            return {"list": self._parse_list(h)}
        except Exception:
            return {"list": []}

    # ===================== 分类 =====================
    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(str(pg) or "1")
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        tid = str(tid or "").strip()
        ext = self._parse_extend(extend)
        # 选中子分类则改用其独立 movtype id
        sub = ext.get("类型") or ext.get("type") or ""
        real_tid = sub if sub else tid
        if not real_tid:
            return {"list": [], "page": pg, "pagecount": pg,
                    "limit": 24, "total": 0}

        url = "%s/movtype/%s/%d.html" % (MAIN, real_tid, pg)
        h = self._req(url)
        lst = self._parse_list(h)

        # 真实末页：取分页链接里同 tid 的最大页号
        nums = re.findall(
            r'/movtype/%s/(\d+)\.html' % re.escape(real_tid), h or "")
        if nums:
            pagecount = max([int(x) for x in nums] + [pg])
        else:
            pagecount = (pg + 1) if lst else pg
        limit = len(lst) or 24
        total = max(limit * pagecount, limit)
        return {"list": lst, "page": pg, "pagecount": pagecount,
                "limit": limit, "total": total}

    # ===================== 详情 =====================
    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        vid = str(vid or "").strip()
        vid = vid.rstrip("/").split("/movdetail/")[-1].split("/")[-1]
        vid = vid.replace(".html", "")
        if not vid:
            return {"list": []}

        h = self._req(MAIN + "/movdetail/" + vid + ".html")

        # 标题
        title = ""
        tm = re.search(r'<span class="name">([^<]+)</span>', h or "")
        if not tm:
            tm = re.search(r'<p class="name[^"]*">([^<]+)</p>', h or "")
        if tm:
            title = self._clean(tm.group(1))
        if not title:
            om = re.search(r'<meta property="og:title" content="([^"]*)"', h or "")
            title = self._clean(om.group(1)) if om else vid

        # 封面（详情主图 class="dpic"，非 "dpic dh" 推荐图）
        pic = ""
        pm = re.search(r'<img[^>]*class="dpic"[^>]*\bsrc="([^"]+)"', h or "")
        if not pm:
            pm = re.search(r'<img[^>]*\bsrc="([^"]+)"[^>]*class="dpic"', h or "")
        if pm:
            pic = pm.group(1)

        # meta: .dlall 内 dt(标签)/dd(值)
        def _meta(label):
            m = re.search(
                r'<dt>\s*%s[：:]*\s*</dt>\s*<dd[^>]*>(.*?)</dd>' % label,
                h or "", re.S)
            return self._clean(m.group(1)) if m else ""

        actor = _meta("主演")
        director = _meta("导演")
        area = _meta("地区")
        year = _meta("年代")
        remark = _meta("备注") or _meta("更新")
        lang = _meta("语言")

        # 简介
        desc = ""
        dm = re.search(r'<div class="des_xy[^"]*">(.*?)</div>', h or "", re.S)
        if dm:
            desc = self._clean(dm.group(1))

        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_year": year,
            "vod_area": area,
            "vod_remarks": remark,
            "vod_actor": actor,
            "vod_director": director,
            "vod_lang": lang,
            "vod_content": desc,
        }

        # 多线路：span#line-N 为线路名，dd.line-N 为该线剧集
        line_names = {}
        for m in re.finditer(r'<span id="line-(\d+)"[^>]*>([^<]*)</span>', h or ""):
            line_names[m.group(1)] = self._clean(m.group(2))

        # dd 块起点（dd 可能带 style，故只锚定起始标签）
        starts = [(m.group(1), m.start())
                  for m in re.finditer(r'<dd class="line-(\d+)[^"]*"', h or "")]
        froms, urls, used = [], [], set()
        for i, (idx, pos) in enumerate(starts):
            end = starts[i + 1][1] if i + 1 < len(starts) else len(h)
            seg = h[pos:end]
            eps = re.findall(
                r'href="(/movplay/[^"]+\.html)"[^>]*>\s*([^<]+?)\s*</a>', seg)
            if not eps:
                continue
            name = line_names.get(idx) or ("线路" + str(int(idx) + 1))
            base, k = name, 2
            while name in used:
                name = "%s%d" % (base, k)
                k += 1
            used.add(name)
            froms.append(name)
            parts = []
            for href, label in eps:
                label = self._clean(label).replace("$", "＄")
                parts.append("%s$%s%s" % (label, MAIN, href))
            urls.append("#".join(parts))

        if froms and urls and len(froms) == len(urls):
            vod["vod_play_from"] = "$$$".join(froms)
            vod["vod_play_url"] = "$$$".join(urls)
        else:
            vod["vod_play_from"] = ""
            vod["vod_play_url"] = ""

        return {"list": [vod]}

    # ===================== 搜索 =====================
    def _ensure_permit(self, return_path):
        """过人机验证，拿 maccms_human_permit cookie（3 小时）。

        关键：服务端会校验「GET 挑战 → POST 校验」之间的真实耗时，
        若过快（滑块交互 < ~0.6s）直接回 400。页面 JS 的 minSubmitMs=550，
        故此处 GET 后必须停顿约 1s 再 POST，并上报一致的 duration_ms。
        """
        if getattr(self, "_permit", None):
            return self._permit
        try:
            hc = MAIN + "/human-check?return=" + quote(return_path, safe="")
            r = self.fetch(hc, headers=self.headers, timeout=20)
            page = (r.text if r else "") or ""
            m = re.search(r'name="challenge"[^>]*value="([^"]+)"', page)
            if not m:
                return ""
            # 模拟滑块交互耗时：停顿后以真实毫秒数上报 duration_ms
            t0 = time.time()
            time.sleep(1.0)
            dur = max(600, int((time.time() - t0) * 1000))
            data = {
                "challenge": m.group(1),
                "return": return_path,
                "duration_ms": str(dur),
                "move_points": "37",
                "final_percent": "100",
                "pressed": "true",
                "released": "true",
            }
            vh = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": MAIN,
                "Referer": hc,
                "User-Agent": UA,
            }
            vr = self.post(MAIN + "/human-check/verify", data=data,
                           headers=vh, timeout=20, allow_redirects=False)
            permit = ""
            if vr is not None:
                chain = [vr] + list(getattr(vr, "history", []) or [])
                for resp in chain:
                    try:
                        c = resp.cookies.get("maccms_human_permit")
                        if c:
                            permit = c
                            break
                    except Exception:
                        pass
                    try:
                        sc = resp.headers.get("Set-Cookie", "") or ""
                        mm = re.search(r'maccms_human_permit=([^;]+)', sc)
                        if mm:
                            permit = mm.group(1)
                            break
                    except Exception:
                        pass
            self._permit = permit
            return permit
        except Exception:
            return ""

    def _permit_cookie(self):
        p = getattr(self, "_permit", None)
        return {"maccms_human_permit": p} if p else None

    def searchContent(self, key, quick, pg="1"):
        try:
            pg = int(str(pg) or "1")
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        key = str(key or "")
        token = base64.urlsafe_b64encode(key.encode("utf-8")).decode().rstrip("=")
        path = "/search/%s/%d.html" % (token, pg)

        self._ensure_permit(path)
        h = self._req(MAIN + path, cookies=self._permit_cookie())
        # 被拦则重取 permit 再试一次
        if (not h) or ("human-check" in h) or ("li_img" not in h):
            self._permit = None
            self._ensure_permit(path)
            h = self._req(MAIN + path, cookies=self._permit_cookie())

        lst = self._parse_list(h)
        return {"list": lst, "page": pg,
                "pagecount": pg + 1 if lst else pg,
                "limit": len(lst) if lst else 24,
                "total": max(len(lst) * (pg + 1), len(lst))}

    # ===================== 播放 =====================
    def _resolve_play(self, movplay_url):
        """movplay 页 → iframe → proxy 接口 → 直链。失败回空串。"""
        try:
            u = movplay_url
            if u.startswith("/"):
                u = MAIN + u
            h = self._req(u)
            if not h:
                return ""
            fm = re.search(r'<iframe[^>]+src="([^"]+)"', h)
            if not fm:
                return ""
            src = _html.unescape(fm.group(1))
            if src.startswith("//"):
                src = "https:" + src
            pr = urlparse(src)
            origin = "%s://%s" % (pr.scheme, pr.netloc)
            qs = parse_qs(pr.query)
            v = (qs.get("v") or qs.get("url") or [""])[0]
            if not v:
                vm = re.search(r'[?&](?:v|url)=([A-Za-z0-9]+)', src)
                v = vm.group(1) if vm else ""
            if not v:
                return ""
            # 取 player.html 内的 proxy 接口基址，拿不到就用 origin/proxy/
            ph = self._req(src, headers={"Referer": MAIN + "/"})
            api = ""
            bm = re.search(r'(https?://[^"\']+/proxy/)', ph or "")
            if bm:
                api = bm.group(1) + v
            else:
                api = origin + "/proxy/" + v
            j = self._req(api, headers={"Accept": "application/json",
                                        "Referer": origin + "/"})
            if j:
                try:
                    d = _json.loads(j)
                    final = (d.get("url") or "").strip()
                    if final:
                        if final.startswith("//"):
                            final = "https:" + final
                        elif final.startswith("/"):
                            final = origin + final
                        return final
                except Exception:
                    pass
            # 旧 playerx/lunli 兜底
            if "playerx" in src.lower():
                return origin + "/lunli/" + v
            return ""
        except Exception:
            return ""

    def playerContent(self, flag, id, vipFlags):
        pid = str(id or "").strip()
        final = self._resolve_play(pid)
        if final:
            # 直链 parse:0；只带 UA（带 Referer 会被源站 403）
            return {"parse": 0, "playUrl": "",
                    "url": final, "header": {"User-Agent": UA}}
        # 兜底：交给解析器
        if pid.startswith("/"):
            pid = MAIN + pid
        return {"parse": 1, "playUrl": "", "url": pid,
                "header": {"User-Agent": UA}}

    # ===================== 相关推荐 =====================
    def recommendContent(self, *args, **kwargs):
        """FongMi 详情页相关推荐：复用详情页内「猜你喜欢」卡片（li_img 同构）。"""
        try:
            ids = args[0] if args else kwargs.get("ids")
            vid = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
            vid = str(vid or "").strip().rstrip("/").split("/movdetail/")[-1]
            vid = vid.split("/")[-1].replace(".html", "")
            if not vid:
                return {"list": []}
            h = self._req(MAIN + "/movdetail/" + vid + ".html")
            lst = [x for x in self._parse_list(h) if x.get("vod_id") != vid]
            return {"list": lst[:18]}
        except Exception:
            return {"list": []}

    # 本地代理：直链无需改写
    def localProxy(self, param):
        return [404, "text/plain", None]
