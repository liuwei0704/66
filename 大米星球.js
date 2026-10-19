/**
 * 大米星球（dmyy22.com / dmyy7.top / dmxq86.com）TVBox / 影视仓 JS 源
 * ------------------------------------------------------------------
 * 站点：苹果CMS V10 + mxtheme 主题（站内真实域名 www.dmxq.fun）
 * 实测语法：
 *   首页      /
 *   分类列表  /vodshow/{12 字段}---.html   ← 字段: 0=tid 1=地区 2=排序 3=剧情 4=语言 8=页码
 *             例: 全部 /vodshow/20-----------.html ；第2页 /vodshow/20--------2---.html
 *                 剧情=Netflix /vodshow/20---Netflix--------.html
 *   搜索      /vodsearch/{关键词}-------------.html      实测可用（48 条/页）
 *   详情      /voddetail/{id}.html                        含线路 tabs 与全部剧集链接
 *   播放      /vodplay/{id}-{sid}-{nid}.html              页内 var player_aaaa = {明文 JSON}
 *
 * 播放地址实测（4 线路样本）：player_aaaa.url 均为 **m3u8 直链**，无需解析
 *   wsym3u8 / bfzym3u8 / jsm3u8 / rym3u8  →  https://.../index.m3u8
 *
 * 契约（本 App 的 JS 桥要求，务必遵守）：
 *   所有方法返回 JSON **字符串**（返回对象会被 Async.call 当 Promise 等 then → 界面空白）
 *   play() 只返回 url（不返回 playUrl，避免地址被拼接）；header 只带 User-Agent
 *   防屏蔽：三域名容灾 + 腾讯/360/阿里 DoH 解析后 IP 直连
 */
const UA = 'Mozilla/5.0 (Linux; Android 13; V2309A Build/TP1A.220624.014; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/116.0.0.0 Mobile Safari/537.36';

const HOSTS = ['https://dmyy22.com', 'https://dmyy7.top', 'https://dmxq86.com'];
const DOH = [
    'https://doh.pub/dns-query?name={h}&type=A',
    'https://doh.360.cn/resolve?name={h}&type=A',
    'https://dns.alidns.com/resolve?name={h}&type=A'
];
const TIMEOUT = 20000;
const SITE = '大米星球';

// 实测有内容的分类（其余 tid 为空分类或资讯栏目）
const CLASSES = [
    { type_id: '35', type_name: '午夜' },
    { type_id: '20', type_name: '电影' },
    { type_id: '21', type_name: '电视剧' },
    { type_id: '22', type_name: '动漫' },
    { type_id: '23', type_name: '综艺' },
    { type_id: '36', type_name: '短剧' }
];

const OPTS = {
    area: ['大陆', '香港', '台湾', '美国', '日本', '韩国', '英国', '法国', '德国', '印度', '泰国'],
    order: [{ n: '时间排序', v: 'time' }, { n: '人气排序', v: 'hits' }, { n: '评分排序', v: 'score' }],
    cls: ['Netflix', '仙侠', '剧情', '科幻', '动作', '喜剧', '爱情', '奇幻', '动画', '恐怖', '惊悚', '丧尸', '战争', '传记', '纪录', '犯罪', '悬疑', '西部'],
    lang: ['国语', '英语', '粤语', '日语', '韩语', '法语', '德语', '俄语', '泰语', '闽南语', '丹麦语']
};
function optList(arr) {
    const out = [{ n: '全部', v: '' }];
    for (let i = 0; i < arr.length; i++) {
        if (typeof arr[i] === 'string') out.push({ n: arr[i], v: arr[i] });
        else out.push(arr[i]);
    }
    return out;
}
function filters() {
    const f = {};
    for (let i = 0; i < CLASSES.length; i++) {
        f[CLASSES[i].type_id] = [
            { key: 'area', name: '地区', value: optList(OPTS.area) },
            { key: 'order', name: '排序', value: optList(OPTS.order) },
            { key: 'cls', name: '剧情', value: optList(OPTS.cls) },
            { key: 'lang', name: '语言', value: optList(OPTS.lang) }
        ];
    }
    return f;
}

let _base = '', _viaDoh = '', _ipHost = '';

/* ---------------- 基础 ---------------- */
function get_(url, referer, extra) {
    try {
        const headers = { 'User-Agent': UA };
        if (referer) headers['Referer'] = referer;
        // IP 直连时必须补 Host（该站按 Host 路由，裸 IP 只返回 155 字节空页）
        if (_ipHost && /^https?:\/\/\d+\.\d+\.\d+\.\d+/.test(url)) headers['Host'] = _ipHost;
        if (extra) for (const k in extra) headers[k] = extra[k];
        const res = req(url, { headers: headers, timeout: TIMEOUT });
        return (res && res.content) ? res.content : '';
    } catch (e) {
        return '';
    }
}
function dohResolveAll(host) {
    for (let i = 0; i < DOH.length; i++) {
        const body = get_(DOH[i].replace('{h}', host), '', { 'Accept': 'application/dns-json' });
        if (!body) continue;
        try {
            const ans = (JSON.parse(body) || {}).Answer || [];
            const ips = [];
            for (let k = 0; k < ans.length; k++) {
                if (ans[k] && (ans[k].type === 1 || ans[k].type === '1') && ans[k].data && ips.indexOf(String(ans[k].data)) < 0) ips.push(String(ans[k].data));
            }
            if (ips.length) return ips;
        } catch (e) { }
    }
    return [];
}
function dohResolve(host) {
    const ips = dohResolveAll(host);
    return ips.length ? ips[0] : '';
}
function hostOk(prefix) {
    const b = get_(prefix + '/vodshow/20-----------.html');
    return b.indexOf('module-item-cover') >= 0;
}
function base() {
    if (_base) return _base;
    for (let i = 0; i < HOSTS.length; i++) {
        if (hostOk(HOSTS[i])) { _base = HOSTS[i]; return _base; }
    }
    // 域名不可用：DoH 解析（腾讯→360→阿里）→ IP 直连 + Host 头；每个域名试前 3 个 IP
    for (let i = 0; i < HOSTS.length; i++) {
        const host = HOSTS[i].replace(/^https?:\/\//, '');
        const ips = dohResolveAll(host);
        for (let k = 0; k < Math.min(ips.length, 3); k++) {
            _ipHost = host;
            if (hostOk('https://' + ips[k])) { _base = 'https://' + ips[k]; _viaDoh = host + ' -> ' + ips[k]; return _base; }
            _ipHost = '';
        }
    }
    _base = HOSTS[0];
    return _base;
}

/* ---------------- 解析工具 ---------------- */
function txt(s) {
    return String(s == null ? '' : s)
        .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&quot;/g, '"')
        .replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>')
        .replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim();
}
function pick(re, s, idx) {
    const m = re.exec(s == null ? '' : s);
    if (!m) return '';
    if (idx == null) idx = m.length > 1 ? 1 : 0;
    return m[idx] == null ? '' : String(m[idx]);
}
function numOf(id) {
    const m = String(id == null ? '' : id).match(/(\d+)/);
    return m ? m[1] : '';
}
function unesc(s) {
    return String(s == null ? '' : s).replace(/\\\//g, '/').replace(/\\"/g, '"').replace(/\\u0026/gi, '&');
}
// HTML 实体还原：站点把封面地址写成 ...&amp;n=0&amp;g=0n... ，
// 不还原的话请求会返回 {"err_no":1,"err_msg":"input data error"} → App 显示不出封面图。
function htmlDec(s) {
    return String(s == null ? '' : s)
        .replace(/&amp;/g, '&').replace(/&#38;/g, '&')
        .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&#34;/g, '"')
        .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&nbsp;/g, ' ')
        .replace(/&#(\d+);/g, function (m, d) { try { return String.fromCharCode(parseInt(d, 10)); } catch (e) { return m; } })
        .trim();
}

// 条目：首页/列表用 a.module-poster-item，搜索页用 a.module-card-item-poster，
// 两者都含 module-item-cover → 以此为标记；<a> 属性顺序不定，故按 href="/voddetail/ 切块。
function parseItems(html) {
    const out = [], seen = {};
    if (!html) return out;
    const parts = String(html).split('href="/voddetail/');
    for (let i = 1; i < parts.length; i++) {
        const s = parts[i].slice(0, 1600);
        if (s.indexOf('module-item-cover') < 0) continue;
        const id = numOf(pick(/^(\d+)\.html/, s));
        if (!id || seen[id]) continue;
        let name = txt(pick(/title="([^"]*)"/, s));
        if (!name) name = txt(pick(/class="module-poster-item-title"[^>]*>([\s\S]{0,90}?)<\/div>/, s));
        if (!name) name = txt(pick(/<img[^>]+alt="([^"]*)"/, s));
        if (!name) continue;
        const pic = htmlDec(pick(/data-original="([^"]+)"/, s) || pick(/<img[^>]+src="(https?:\/\/[^"]+)"/, s));
        const note = txt(pick(/class="module-item-note"[^>]*>([\s\S]{0,30}?)<\/div>/, s));
        const score = txt(pick(/class="module-item-douban"[^>]*>([\s\S]{0,24}?)<\/div>/, s));
        const cls = txt(pick(/class="module-card-item-class"[^>]*>([\s\S]{0,20}?)<\/div>/, s));
        seen[id] = 1;
        out.push({
            vod_id: id,
            vod_name: name,
            vod_pic: pic,
            vod_remarks: note ? (note + (score ? ' ' + score : '')) : (score || cls)
        });
    }
    return out;
}
function pageMax(html) {
    let max = 1, m;
    const re = /\/vodshow\/[^"'\/]*?-(\d+)---\.html/g;
    while ((m = re.exec(html || '')) !== null) { const v = parseInt(m[1], 10) || 1; if (v > max) max = v; }
    return max;
}

/* ---------------- 源实现（全部返回 JSON 字符串） ---------------- */
export default {
    init: function (cfg) {
        _base = '';
        _viaDoh = '';
        _ipHost = '';
        return true;
    },

    home: function (filter) {
        return JSON.stringify({ class: CLASSES, filters: filters() });
    },

    homeVod: function () {
        return JSON.stringify({ list: parseItems(get_(base() + '/', base() + '/')) });
    },

    category: function (tid, pg, filter, extend) {
        pg = parseInt(pg, 10) || 1;
        tid = numOf(tid) || '20';
        const ext = extend || {};
        const f = ['', '', '', '', '', '', '', '', '', '', '', ''];
        f[0] = tid;
        f[1] = ext.area ? String(ext.area) : '';
        f[2] = ext.order ? String(ext.order) : '';
        f[3] = ext.cls ? String(ext.cls) : '';
        f[4] = ext.lang ? String(ext.lang) : '';
        f[8] = pg > 1 ? String(pg) : '';
        // 12 个字段用 - 连接即为完整路径片段（11 个分隔符），末尾不再补 ---
        const url = base() + '/vodshow/' + f.join('-') + '.html';
        let html = get_(url, base() + '/');
        let items = parseItems(html);
        if (pg > 1 && !items.length) {
            // 带筛选翻页偶发失效：改从第 1 页的分页链接里取真实第 N 页地址
            const f1 = f.slice(); f1[8] = '';
            const first = get_(base() + '/vodshow/' + f1.join('-') + '.html', base() + '/');
            const link = pick(new RegExp('href="(/vodshow/[^"]*?-' + pg + '---\\.html)"'), first);
            if (link) { html = get_(base() + link, base() + '/'); items = parseItems(html); }
        }
        const pc = pageMax(html);
        return JSON.stringify({
            list: items,
            page: pg,
            pagecount: pc > 1 ? pc : (items.length ? pg + 1 : pg),
            limit: items.length,
            total: pc * 40
        });
    },

    detail: function (id) {
        const num = numOf(id);
        const page = base() + '/voddetail/' + num + '.html';
        const html = get_(page, base() + '/');
        const vod = {
            vod_id: num,
            vod_name: '', vod_pic: '', vod_remarks: '', type_name: '',
            vod_year: '', vod_area: '', vod_actor: '', vod_director: '',
            vod_content: '', vod_play_from: SITE, vod_play_url: ''
        };
        if (!html || html.indexOf('module-info') < 0) return JSON.stringify({ list: [] });

        vod.vod_name = txt(pick(/<h1[^>]*>\s*<a[^>]*title="([^"]*)"/, html)) ||
            txt(pick(/<h1[^>]*>([\s\S]{0,120}?)<\/h1>/, html)) ||
            txt(pick(/<title>([\s\S]{0,100}?)<\/title>/, html)).split(/[-_]/)[0];
        // 封面：详情页 data-original 常为空串，真地址在 src；且页面首个 img 是站点 logo
        // → 限定在 module-info-poster 区块内取；结果必须做 HTML 实体还原（&amp; → &）
        vod.vod_pic = htmlDec(pick(/class="module-info-poster"[\s\S]{0,700}?data-original="([^"]+)"/, html) ||
            pick(/class="module-info-poster"[\s\S]{0,700}?<img[^>]+src="(https?:\/\/[^"]+)"/, html) ||
            pick(/data-original="([^"]+)"/, html));
        vod.vod_content = txt(pick(/class="module-info-introduction-content[^"]*"[^>]*>([\s\S]{0,1500}?)<\/div>\s*<\/div>/, html)) ||
            txt(pick(/class="module-info-introduction-content[^"]*"[^>]*>([\s\S]{0,1500}?)<\/div>/, html));

        // 信息行：年份 / 地区 / 类型（一个块可能含多个 <a>，且块内容可能很长 → 按块标记切分）
        const tagParts = html.split('<div class="module-info-tag-link">');
        for (let i = 1; i < tagParts.length; i++) {
            const rest = tagParts[i];
            const cut = rest.indexOf('</div>');
            const blk = cut >= 0 ? rest.slice(0, cut) : rest.slice(0, 1500);
            const anchors = [...blk.matchAll(/<a[^>]*>([\s\S]{0,40}?)<\/a>/g)].map((x) => txt(x[1])).filter(Boolean);
            const vals = anchors.length ? anchors : [txt(blk)];
            for (let k = 0; k < vals.length; k++) {
                const t = vals[k];
                if (!t) continue;
                if (/^(19|20)\d{2}$/.test(t)) { if (!vod.vod_year) vod.vod_year = t; continue; }
                if (/^(主演|演员)/.test(t) || t.length > 24) { if (!vod.vod_actor) vod.vod_actor = t.replace(/^(主演|演员)[：:]\s*/, ''); continue; }
                if (/^导演/.test(t)) { if (!vod.vod_director) vod.vod_director = t.replace(/^导演[：:]\s*/, ''); continue; }
                if (/^(中国大陆|中国香港|中国台湾|大陆|香港|台湾|美国|日本|韩国|英国|法国|德国|泰国|印度|加拿大|澳大利亚|Netflix)$/.test(t)) { if (!vod.vod_area) vod.vod_area = t; continue; }
                if (t.length <= 10 && !vod.type_name) vod.type_name = t;
            }
        }
        vod.vod_remarks = txt(pick(/class="module-item-note"[^>]*>([\s\S]{0,24}?)<\/div>/, html));

        // 线路名（tabs 顺序）
        const tabs = [...html.matchAll(/data-dropdown-value="([^"]*)"/g)].map((m) => txt(m[1]));
        // 剧集：按 class="module-play-list-link" 切块（该主题 class 在 href 之前）
        const groups = {}, order = [];
        const segs = html.split('class="module-play-list-link"');
        for (let i = 1; i < segs.length; i++) {
            const s = segs[i].slice(0, 500);
            const href = pick(/href="(\/vodplay\/\d+-\d+-\d+\.html)"/, s);
            if (!href) continue;
            const sid = pick(/\/vodplay\/\d+-(\d+)-\d+\.html/, href);
            if (!sid) continue;
            let title = txt(pick(/title="([^"]*)"/, s));
            const sp = txt(s.slice(s.indexOf('>') + 1, s.indexOf('</a>')));
            if (sp) title = sp;
            if (!groups[sid]) { groups[sid] = []; order.push(sid); }
            groups[sid].push((title || ('第' + pick(/\/vodplay\/\d+-\d+-(\d+)\.html/, href) + '集')) + '$' + href);
        }
        const froms = [], urls = [];
        for (let i = 0; i < order.length; i++) {
            const eps = groups[order[i]];
            if (!eps || !eps.length) continue;
            const nm = (tabs.length === order.length && tabs[i]) ? tabs[i] : ('线路' + order[i]);
            froms.push(nm);
            urls.push(eps.join('#'));
        }
        if (froms.length) {
            vod.vod_play_from = froms.join('$$$');
            vod.vod_play_url = urls.join('$$$');
        } else {
            vod.vod_play_from = SITE;
            vod.vod_play_url = '立即播放$/vodplay/' + num + '-1-1.html';
        }
        return JSON.stringify({ list: [vod] });
    },

    play: function (flag, id, flags) {
        let url = String(id == null ? '' : id).trim();
        if (!/^https?:\/\//i.test(url)) {
            const s = url.charAt(0) === '/' ? url : ('/vodplay/' + url);
            const html = get_(base() + s, base() + '/voddetail/' + numOf(s) + '.html');
            const raw = pick(/var\s+player_aaaa\s*=\s*(\{[\s\S]*?\})\s*;?\s*<\//, html);
            let u = '';
            if (raw) { try { u = String(JSON.parse(unesc(raw)).url || ''); } catch (e) { u = ''; } }
            if (!u) u = unesc(pick(/"(?:url|url_next)"\s*:\s*"(https?:[^"]+?)"/, html));
            if (!u) u = unesc(pick(/(https?:\/\/[^\s"'<>\\]+\.m3u8[^\s"'<>\\]*)/, html));
            url = u || url;
        }
        // 只返回 url：不返回 playUrl（App 会把两者相加导致播不了）；header 只带 UA
        return JSON.stringify({
            parse: 0,
            jx: 0,
            url: url,
            msg: /^https?:\/\//i.test(url) ? '' : '未解析到播放地址',
            header: JSON.stringify({ 'User-Agent': UA })
        });
    },

    search: function (wd, quick, pg) {
        const kw = String(wd == null ? '' : wd).trim();
        if (!kw) return JSON.stringify({ list: [] });
        pg = parseInt(pg, 10) || 1;
        const html = get_(base() + '/vodsearch/' + encodeURIComponent(kw) + '-------------.html', base() + '/');
        let items = parseItems(html);
        if (pg > 1) {
            const link = pick(new RegExp('href="(/vodsearch/[^"]*?-' + pg + '---\\.html)"'), html);
            if (link) items = parseItems(get_(base() + link, base() + '/'));
        }
        return JSON.stringify({ list: items });
    },

    sniffer: function () {
        return false;
    },

    isVideo: function (url) {
        return /\.(m3u8|mp4)(\?|$)/i.test(String(url || ''));
    }
};
