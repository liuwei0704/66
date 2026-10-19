/*
====================================================================
 极光影视（hellociqryx6e.com）—— 安忆TVBOX / JsSpider 模块格式 JS 源
====================================================================
 用法（sites 里加一条，api 必须指向 .js）：
   {
     "key": "jiguang",
     "name": "🌌极光影视",
     "type": 3,
     "api": "https://你的地址/hellociqryx6e.js",
     "searchable": 1,
     "quickSearch": 1,
     "filterable": 1,
     "timeout": 60
   }

 站点结构（Next.js 前端 + mw-movie 后端 API）：
   前端: https://hellociqryx6e.com     详情 /detail/{vodId}
   接口: https://m.hellociqryx6e.com/api/mw-movie   ← 站点 /api 会 302 到这里
   接口清单: /anonymous/video/list          分类列表(type1=频道, pageNum 翻页)
             /anonymous/video/detail?id=     详情(含 episodeList[{nid,name}])
             /anonymous/v2/video/episode/url?id=&nid=&clientType=3   取播放地址
             /anonymous/video/searchByWordPageable?keyword=&pageNum=&pageSize=
  签名(从站点 JS 还原, 模块 22331::sign):
     s = 参数按 key 升序拼 "k=v&k=v" + "&key=" + SIGN_KEY + "&t=" + Date.now()
     sign = SHA1( MD5(s) )        ← 注意: 先 MD5 再 SHA1, 不是双重 MD5
     请求头: sign / t / deviceId / client-type: 3 / authorization: ''
  筛选值用中文: v_class=喜剧  area=中国大陆  year=2026  lang=国语  (sort: 1上映 3人气 4评分)
  播放返回 data.list[]: [{resolution, resolutionName, needLogin, url}] —— 实测各清晰度均可直连,
  且分片对 Referer 无要求(header 只带 UA 最稳)。
====================================================================
*/

/* ============================== 常量 ============================== */
var JG_SITE = 'https://hellociqryx6e.com';
var JG_API = 'https://m.hellociqryx6e.com/api/mw-movie';
var JG_SIGN_KEY = 'cb808529bae6b6be45ecfab29a4889bc';
var JG_UA = 'Mozilla/5.0 (Linux; Android 13; V2309A Build/TP1A.220624.014; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/116.0.0.0 Mobile Safari/537.36';
var JG_DEVICE = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee';

/* ============================== 编码/哈希 ============================== */
function jgUtf8(str) {
    var out = [], i, c, c2, cp;
    str = String(str);
    for (i = 0; i < str.length; i++) {
        c = str.charCodeAt(i);
        if (c < 0x80) out.push(c);
        else if (c < 0x800) out.push(0xc0 | (c >> 6), 0x80 | (c & 63));
        else if (c >= 0xd800 && c <= 0xdbff) {
            c2 = str.charCodeAt(++i);
            cp = 0x10000 + ((c - 0xd800) << 10) + (c2 - 0xdc00);
            out.push(0xf0 | (cp >> 18), 0x80 | ((cp >> 12) & 63), 0x80 | ((cp >> 6) & 63), 0x80 | (cp & 63));
        } else out.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
    }
    return out;
}

function jgHex(bytes) {
    var s = '', i, h;
    for (i = 0; i < bytes.length; i++) { h = bytes[i].toString(16); s += (h.length < 2 ? '0' + h : h); }
    return s;
}

/* MD5（与 CryptoJS 一致：K[i] = floor(abs(sin(i+1)) * 2^32)） */
function jgMd5Bytes(bytes) {
    function rl(x, n) { return ((x << n) | (x >>> (32 - n))) >>> 0; }
    function add(a, b) { return (a + b) >>> 0; }
    var K = [], i;
    for (i = 0; i < 64; i++) K[i] = (Math.floor(Math.abs(Math.sin(i + 1)) * 4294967296)) >>> 0;
    var S = [7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22,
             5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20,
             4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23,
             6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21];
    var len = bytes.length;
    var withPad = len + 1;
    var total = (((withPad + 8 + 63) >> 6) << 6);
    var m = [], j;
    for (i = 0; i < total; i++) m[i] = 0;
    for (i = 0; i < len; i++) m[i] = bytes[i] & 255;
    m[len] = 0x80;
    var bits = len * 8;
    var hi = Math.floor(bits / 4294967296), lo = bits >>> 0;
    m[total - 8] = lo & 255; m[total - 7] = (lo >>> 8) & 255; m[total - 6] = (lo >>> 16) & 255; m[total - 5] = (lo >>> 24) & 255;
    m[total - 4] = hi & 255; m[total - 3] = (hi >>> 8) & 255; m[total - 2] = (hi >>> 16) & 255; m[total - 1] = (hi >>> 24) & 255;

    var a = 1732584193, b = 4023233417, c = 2562383102, d = 271733878;
    var w = [], o, f, g, tmp;
    for (o = 0; o < total; o += 64) {
        for (i = 0; i < 16; i++) {
            w[i] = (m[o + i * 4] | (m[o + i * 4 + 1] << 8) | (m[o + i * 4 + 2] << 16) | (m[o + i * 4 + 3] << 24)) >>> 0;
        }
        var aa = a, bb = b, cc = c, dd = d;
        for (i = 0; i < 64; i++) {
            if (i < 16) { f = ((bb & cc) | ((~bb >>> 0) & dd)) >>> 0; g = i; }
            else if (i < 32) { f = ((dd & bb) | ((~dd >>> 0) & cc)) >>> 0; g = (5 * i + 1) % 16; }
            else if (i < 48) { f = (bb ^ cc ^ dd) >>> 0; g = (3 * i + 5) % 16; }
            else { f = (cc ^ (bb | (~dd >>> 0))) >>> 0; g = (7 * i) % 16; }
            tmp = dd;
            dd = cc; cc = bb;
            var sum = add(add(add(aa, f), add(K[i], w[g])), 0);
            bb = add(bb, rl(sum, S[i]));
            aa = tmp;
        }
        a = add(a, aa); b = add(b, bb); c = add(c, cc); d = add(d, dd);
    }
    var out = [];
    [a, b, c, d].forEach(function (x) {
        out.push(x & 255, (x >>> 8) & 255, (x >>> 16) & 255, (x >>> 24) & 255);
    });
    return out;
}

function jgMd5(str) { return jgHex(jgMd5Bytes(jgUtf8(str))); }

/* SHA1 */
function jgSha1Bytes(bytes) {
    function rl(x, n) { return ((x << n) | (x >>> (32 - n))) >>> 0; }
    var len = bytes.length;
    var total = (((len + 1 + 8 + 63) >> 6) << 6);
    var m = [], i;
    for (i = 0; i < total; i++) m[i] = 0;
    for (i = 0; i < len; i++) m[i] = bytes[i] & 255;
    m[len] = 0x80;
    var bits = len * 8, hi = Math.floor(bits / 4294967296), lo = bits >>> 0;
    m[total - 8] = (hi >>> 24) & 255; m[total - 7] = (hi >>> 16) & 255; m[total - 6] = (hi >>> 8) & 255; m[total - 5] = hi & 255;
    m[total - 4] = (lo >>> 24) & 255; m[total - 3] = (lo >>> 16) & 255; m[total - 2] = (lo >>> 8) & 255; m[total - 1] = lo & 255;

    var h0 = 1732584193, h1 = 4023233417, h2 = 2562383102, h3 = 271733878, h4 = 3285377520;
    var w = [], o, t, j;
    for (o = 0; o < total; o += 64) {
        for (i = 0; i < 16; i++) {
            w[i] = ((m[o + i * 4] << 24) | (m[o + i * 4 + 1] << 16) | (m[o + i * 4 + 2] << 8) | m[o + i * 4 + 3]) >>> 0;
        }
        for (i = 16; i < 80; i++) w[i] = rl(w[i - 3] ^ w[i - 8] ^ w[i - 14] ^ w[i - 16], 1);
        var a = h0, b = h1, c = h2, d = h3, e = h4, f, k;
        for (i = 0; i < 80; i++) {
            if (i < 20) { f = ((b & c) | ((~b >>> 0) & d)) >>> 0; k = 1518500249; }
            else if (i < 40) { f = (b ^ c ^ d) >>> 0; k = 1859775393; }
            else if (i < 60) { f = ((b & c) | (b & d) | (c & d)) >>> 0; k = 2400959708; }
            else { f = (b ^ c ^ d) >>> 0; k = 3395469782; }
            t = (((rl(a, 5) + f) >>> 0) + ((e + k) >>> 0)) >>> 0;
            t = (t + w[i]) >>> 0;
            e = d; d = c; c = rl(b, 30); b = a; a = t;
        }
        h0 = (h0 + a) >>> 0; h1 = (h1 + b) >>> 0; h2 = (h2 + c) >>> 0; h3 = (h3 + d) >>> 0; h4 = (h4 + e) >>> 0;
    }
    var out = [];
    [h0, h1, h2, h3, h4].forEach(function (x) {
        out.push((x >>> 24) & 255, (x >>> 16) & 255, (x >>> 8) & 255, x & 255);
    });
    return out;
}

function jgSha1(str) { return jgHex(jgSha1Bytes(jgUtf8(str))); }

/* ============================== HTTP ============================== */
function jgReq(url, headers) {
    var g = (typeof globalThis !== 'undefined') ? globalThis : null;
    var f = (typeof req === 'function') ? req : (g && typeof g.req === 'function' ? g.req : null);
    if (!f) return '';
    var r = null;
    try { r = f(url, { headers: headers || { 'User-Agent': JG_UA } }); } catch (e) { return ''; }
    if (r === null || r === undefined) return '';
    if (typeof r === 'string') return r;
    if (typeof r === 'object') {
        if (typeof r.content === 'string') return r.content;
        if (typeof r.body === 'string') return r.body;
        if (r.content !== undefined && r.content !== null) return '' + r.content;
    }
    return '' + r;
}

function jgEnc(v) { return encodeURIComponent(String(v)); }

/* 生成签名并请求接口 */
function jgApi(path, params) {
    var clean = {}, k;
    for (k in params) {
        if (!params.hasOwnProperty(k)) continue;
        var v = params[k];
        if (v === undefined || v === null || v === '') continue;
        clean[k] = v;
    }
    var keys = [];
    for (k in clean) if (clean.hasOwnProperty(k)) keys.push(k);
    keys.sort();
    var qs = [], i;
    for (i = 0; i < keys.length; i++) qs.push(keys[i] + '=' + clean[keys[i]]);   // 签名用原始值
    var raw = qs.join('&');
    var t = (new Date()).getTime();
    var s = (raw ? raw + '&' : '') + 'key=' + JG_SIGN_KEY + '&t=' + t;
    var sign = jgSha1(jgMd5(s));
    var enc = [];
    for (i = 0; i < keys.length; i++) enc.push(keys[i] + '=' + jgEnc(clean[keys[i]]));
    var url = JG_API + path + (enc.length ? '?' + enc.join('&') : '');
    var body = jgReq(url, {
        'User-Agent': JG_UA,
        'Accept': 'application/json, text/plain, */*',
        'sign': sign,
        't': String(t),
        'deviceId': JG_DEVICE,
        'authorization': '',
        'client-type': '3',
        'Referer': JG_SITE + '/',
        'Origin': JG_SITE
    });
    try { return JSON.parse(body); } catch (e) { return null; }
}

/* ============================== 解析 ============================== */
function jgItems(list) {
    var out = [], i;
    list = list || [];
    for (i = 0; i < list.length; i++) {
        var it = list[i] || {};
        if (!it.vodId) continue;
        var rem = [];
        if (it.vodScore) rem.push(String(it.vodScore));
        if (it.vodRemarks) rem.push(String(it.vodRemarks));
        else if (it.vodClass) rem.push(String(it.vodClass).split(',')[0]);
        out.push({
            vod_id: String(it.vodId),
            vod_name: it.vodName || '',
            vod_pic: it.vodPic || '',
            vod_remarks: rem.join(' ')
        });
    }
    return out;
}

var JG_CLASSES = [
    { type_id: '1', type_name: '电影' },
    { type_id: '2', type_name: '电视剧' },
    { type_id: '3', type_name: '综艺' },
    { type_id: '4', type_name: '动漫' }
];

var JG_PLOTS = ['喜剧', '动作', '爱情', '科幻', '悬疑', '奇幻', '恐怖', '剧情', '犯罪', '动画', '惊悚', '战争', '冒险', '灾难', '伦理', '其他'];
var JG_AREAS = ['中国大陆', '中国香港', '中国台湾', '美国', '日本', '韩国', '印度', '泰国', '英国', '法国', '其他'];
var JG_LANGS = ['国语', '英语', '粤语', '韩语', '日语', '其他'];
var JG_YEARS = (function () {
    var a = [], y;
    for (y = 2026; y >= 2010; y--) a.push(String(y));
    a.push('2009~2000');
    return a;
})();

function jgOpts(arr) {
    var out = [{ n: '全部', v: '' }], i;
    for (i = 0; i < arr.length; i++) out.push({ n: arr[i], v: arr[i] });
    return out;
}

function jgFilters() {
    var f = {}, i;
    for (i = 0; i < JG_CLASSES.length; i++) {
        f[JG_CLASSES[i].type_id] = [
            { key: 'v_class', name: '剧情', value: jgOpts(JG_PLOTS) },
            { key: 'area', name: '地区', value: jgOpts(JG_AREAS) },
            { key: 'year', name: '年份', value: jgOpts(JG_YEARS) },
            { key: 'lang', name: '语言', value: jgOpts(JG_LANGS) },
            { key: 'sort', name: '排序', value: [{ n: '最新', v: '1' }, { n: '人气', v: '3' }, { n: '评分', v: '4' }] }
        ];
    }
    return f;
}

/* ============================== 模块导出 ============================== */
export default {
    init: function (cfg) {
        try {
            var c = cfg;
            if (typeof c === 'string' && c.indexOf('{') === 0) c = JSON.parse(c);
            if (c && c.api) JG_API = String(c.api).replace(/\/+$/, '');
            if (c && c.site) JG_SITE = String(c.site).replace(/\/+$/, '');
        } catch (e) { }
        return true;
    },

    home: function (filter) {
        return JSON.stringify({ class: JG_CLASSES, filters: jgFilters() });
    },

    homeVod: function () {
        // 该接口不带 type1 时返回空, 所以按四个频道各取一页再合并
        var chans = ['1', '2', '3', '4'], items = [], seen = {}, i, k;
        for (i = 0; i < chans.length; i++) {
            var j = jgApi('/anonymous/video/list', { pageNum: 1, pageSize: 8, type1: chans[i], sort: 1, sortBy: 1 });
            var l = (j && j.data && j.data.list) || [];
            for (k = 0; k < l.length; k++) {
                var vid = String(l[k].vodId || '');
                if (vid && !seen[vid]) { seen[vid] = 1; items.push(l[k]); }
            }
        }
        return JSON.stringify({ list: jgItems(items) });
    },

    category: function (tid, pg, filter, extend) {
        var ext = extend || {};
        var params = {
            pageNum: parseInt(pg, 10) || 1,
            pageSize: 30,
            sort: ext.sort || 1,
            sortBy: 1
        };
        if (tid) params.type1 = tid;
        if (ext.v_class) params.v_class = ext.v_class;
        if (ext.area) params.area = ext.area;
        if (ext.year) params.year = ext.year;
        if (ext.lang) params.lang = ext.lang;
        var j = jgApi('/anonymous/video/list', params);
        var list = (j && j.data && j.data.list) || [];
        var total = (j && j.data && j.data.totalCount) || 0;
        var totalPage = (j && j.data && j.data.totalPage) || 9999;
        return JSON.stringify({
            list: jgItems(list),
            page: parseInt(pg, 10) || 1,
            pagecount: totalPage > 0 ? totalPage : 9999,
            limit: 30,
            total: total || 9999
        });
    },

    detail: function (id) {
        var vid = ('' + id).replace(/^.*\/detail\//, '').split('?')[0];
        var j = jgApi('/anonymous/video/detail', { id: vid });
        var d = (j && j.data) || null;
        if (!d) return JSON.stringify({ list: [] });
        var eps = d.episodeList || [];
        var arr = [], i;
        for (i = 0; i < eps.length; i++) {
            var nm = eps[i].name || String(i + 1);
            if (nm.indexOf('\u7b2c') !== 0 && /^\d+$/.test(nm)) nm = '\u7b2c' + nm + '\u96c6';   // 第N集
            arr.push(nm + '$' + vid + '|' + eps[i].nid);
        }
        if (!arr.length) arr.push('\u64ad\u653e$' + vid + '|');
        var content = [];
        if (d.vodContent) content.push(String(d.vodContent).replace(/<[^>]+>/g, ''));
        if (d.vodDirector) content.push('\u5bfc\u6f14: ' + d.vodDirector);
        if (d.vodActor) content.push('\u4e3b\u6f14: ' + d.vodActor);
        if (d.vodScore) content.push('\u8bc4\u5206: ' + d.vodScore);
        return JSON.stringify({
            list: [{
                vod_id: vid,
                vod_name: d.vodName || vid,
                vod_pic: d.vodPic || '',
                type_name: d.typeName || '',
                vod_year: d.vodYear || '',
                vod_area: d.vodArea || '',
                vod_actor: d.vodActor || '',
                vod_director: d.vodDirector || '',
                vod_remarks: d.vodRemarks || '',
                vod_content: content.join('\n'),
                vod_play_from: '\u6781\u5149\u5f71\u89c6',
                vod_play_url: arr.join('#')
            }]
        });
    },

    search: function (wd, quick) {
        var j = jgApi('/anonymous/video/searchByWordPageable', { keyword: wd, pageNum: 1, pageSize: 30 });
        var list = (j && j.data && j.data.list) || [];
        return JSON.stringify({ list: jgItems(list) });
    },

    play: function (flag, id, flags) {
        var s = '' + id, p = s.indexOf('|');
        var vid = p > 0 ? s.substring(0, p) : s;
        var nid = p > 0 ? s.substring(p + 1) : '';
        if (!vid || !nid) return JSON.stringify({ parse: 0, jx: 0, url: '', msg: '\u7f3a\u5c11\u64ad\u653e\u53c2\u6570', header: '' });
        var j = jgApi('/anonymous/v2/video/episode/url', { clientType: 3, id: vid, nid: nid });
        var list = (j && j.data && j.data.list) || [];
        var best = '', i;
        for (i = 0; i < list.length; i++) {
            if (list[i] && list[i].resolution === 1080 && list[i].url) { best = list[i].url; break; }
        }
        if (!best) for (i = 0; i < list.length; i++) {
            if (list[i] && list[i].resolution === 720 && list[i].url) { best = list[i].url; break; }
        }
        if (!best) for (i = 0; i < list.length; i++) {
            if (list[i] && list[i].url) { best = list[i].url; break; }
        }
        // header 只带 UA: 分片服务器对 Referer 无要求/可能拒绝, 保持最小化最稳
        return JSON.stringify({
            parse: 0,
            jx: 0,
            url: best,
            msg: best ? '' : ((j && j.msg) || '\u83b7\u53d6\u64ad\u653e\u5730\u5740\u5931\u8d25'),
            header: JSON.stringify({ 'User-Agent': JG_UA })
        });
    }
};
