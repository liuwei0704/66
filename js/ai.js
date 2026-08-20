import 'assets://js/lib/crypto-js.js';

const CryptoJS = globalThis.CryptoJS;
const USER_AGENT = 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36';
const IMAGE_KEY = 'f5d965df75336270';
const IMAGE_IV = '97b60394abc2fbe1';

const DEFAULT_CONFIG = {
  siteBase: 'https://huangguoai.com',
  timeoutMs: 15000,
  categories: [
    { type_id: 'ai-duanju', type_name: 'AI成人短剧' },
    { type_id: 'ai-manju', type_name: 'AI成人漫剧' },
    { type_id: 'ai-huanlian', type_name: 'AI换脸' },
    { type_id: 'ai-mogai', type_name: 'AI魔改' }
  ],
  filters: {}
};

const state = {
  config: { ...DEFAULT_CONFIG },
  transport: null,
  lastError: ''
};

function init(context, extend) {
  const input = extend === undefined ? context : extend;
  state.config = normalizeConfig(parseExtend(input));
  state.lastError = '';
  return '{}';
}

function home(filter) {
  const output = {
    class: state.config.categories.map((item) => ({
      type_id: String(item.type_id || item.id || ''),
      type_name: String(item.type_name || item.name || '')
    })).filter((item) => item.type_id && item.type_name)
  };
  if (filter) output.filters = state.config.filters;
  return stringify(output);
}

function homeVod() {
  try {
    return stringify({ list: extractCards(requestText('/')) });
  } catch (error) {
    return failList(error);
  }
}

function category(tid, pg, filter, extend) {
  const page = clampPage(pg);
  const typeId = String(tid || '');
  const allowed = state.config.categories.some((item) => String(item.type_id || item.id) === typeId);
  if (!allowed) return stringify(pagedResult([], page, 1, 0));

  try {
    const html = requestText(categoryPath(typeId, page));
    const list = extractCards(html);
    const pagecount = Number((html.match(/data-pages="(\d+)"/i) || [])[1] || 1);
    return stringify(pagedResult(list, page, pagecount, pagecount * (list.length || 20)));
  } catch (error) {
    return failPage(error, page);
  }
}

function detail(ids) {
  const videoId = normalizeId(ids).match(/\d+/);
  if (!videoId) return stringify({ list: [] });

  try {
    const html = requestText('/video/' + videoId[0] + '/');
    const data = parseInitialData(html);
    const episodes = extractEpisodes(html);
    if (episodes.length === 0 && (data.videoSrc || ((data.epPlaySrcs || {})[data.ep]))) {
      episodes.push({ number: 1, url: absoluteUrl('/video/' + videoId[0] + '/') });
    }
    const urls = episodes.map((episode) => {
      const label = '第' + String(episode.number).padStart(2, '0') + '集';
      return label + '$' + episode.url;
    });
    const typeName = (data.breadcrumb || []).map((item) => item.name).filter(Boolean).join(' / ');
    return stringify({
      list: [{
        vod_id: videoId[0],
        vod_name: data.title || '',
        vod_pic: imageProxyUrl(absoluteUrl(data.coverSrc || data.posterSrc)),
        type_name: typeName,
        vod_year: String(data.time || '').slice(0, 4),
        vod_area: '',
        vod_actor: data.author || '',
        vod_director: '',
        vod_remarks: data.ep ? '更新至' + data.ep + '集' : '',
        vod_content: data.description || '',
        vod_play_from: '黄果短剧',
        vod_play_url: urls.join('#')
      }]
    });
  } catch (error) {
    state.lastError = error.message || String(error);
    return stringify({ list: [] });
  }
}

function search(key, quick, pg) {
  const page = clampPage(pg);
  const keyword = String(key || '').trim();
  if (!keyword) return stringify(pagedResult([], page, 1, 0));

  try {
    const html = requestText('/search/video/' + encodeURIComponent(keyword) + '/');
    const list = extractCards(html);
    return stringify(pagedResult(list, page, 1, list.length));
  } catch (error) {
    return failPage(error, page);
  }
}

function play(flag, id, flags) {
  try {
    const html = requestText(id);
    const data = parseInitialData(html);
    const url = data.videoSrc || ((data.epPlaySrcs || {})[data.ep]);
    if (!url) return stringify({ parse: 0, jx: 0, url: '' });
    return stringify({
      parse: 0,
      jx: 0,
      url,
      header: requestHeaders()
    });
  } catch (error) {
    state.lastError = error.message || String(error);
    return stringify({ parse: 0, jx: 0, url: '' });
  }
}

// 第 5 项为 1 时，第 3 项按 Base64 还原成响应字节。
function proxy(params) {
  const url = String((params && params.url) || '');

  try {
    const cipherBase64 = requestBase64(url);
    const plain = CryptoJS.AES.decrypt(cipherBase64, CryptoJS.enc.Utf8.parse(IMAGE_KEY), {
      iv: CryptoJS.enc.Utf8.parse(IMAGE_IV),
      mode: CryptoJS.mode.CBC,
      padding: CryptoJS.pad.NoPadding
    });
    const imageBase64 = CryptoJS.enc.Base64.stringify(plain);
    if (!imageBase64) throw new Error('Image decrypt returned no data.');
    return [
      200,
      'image/jpeg',
      imageBase64,
      { 'Cache-Control': 'public, max-age=86400' },
      1
    ];
  } catch (error) {
    state.lastError = error.message || String(error);
    return [502, 'text/plain; charset=utf-8', 'Image decrypt failed'];
  }
}

function homeContent(filter) {
  return home(filter);
}

function homeVideoContent() {
  return homeVod();
}

function categoryContent(tid, pg, filter, extend) {
  return category(tid, pg, filter, extend);
}

function detailContent(ids) {
  return detail(ids);
}

function searchContent(key, quick, pg) {
  return search(key, quick, pg);
}

function playerContent(flag, id, flags) {
  return play(flag, id, flags);
}

function destroy() {
  state.transport = null;
  state.lastError = '';
  return '{}';
}

function setTransport(transport) {
  state.transport = typeof transport === 'function' ? transport : null;
}

function getConfig() {
  return { ...state.config, categories: state.config.categories.slice() };
}

function getLastError() {
  return state.lastError;
}

function requestText(path) {
  return normalizeResponse(requestRaw(path));
}

function requestBase64(path) {
  const response = requestRaw(path, { buffer: 2 });
  if (response && typeof response.then === 'function') {
    throw new Error('Request helper returned a Promise; this Spider needs synchronous requests.');
  }
  const content = response && (response.content || response.body || response.data);
  if (typeof content !== 'string' || !content) {
    throw new Error('Request returned no Base64 binary content.');
  }
  return content;
}

function requestRaw(path, extraOptions) {
  const url = absoluteUrl(path);
  const options = Object.assign({
    method: 'GET',
    async: false,
    headers: requestHeaders(),
    timeout: state.config.timeoutMs
  }, extraOptions || {});
  return state.transport
    ? state.transport(url, options)
    : getRequestFunction()(url, options);
}

function getRequestFunction() {
  const request = globalThis.req || globalThis.request;
  if (typeof request !== 'function') {
    throw new Error('No synchronous request helper is available.');
  }
  return request;
}

function normalizeResponse(response) {
  if (typeof response === 'string') return response;
  if (response && typeof response.then === 'function') {
    throw new Error('Request helper returned a Promise; this Spider needs synchronous requests.');
  }
  if (response && typeof response.content === 'string') return response.content;
  if (response && typeof response.body === 'string') return response.body;
  if (response && typeof response.data === 'string') return response.data;
  if (response && typeof response.text === 'string') return response.text;
  throw new Error('Request returned no text content.');
}

function requestHeaders() {
  return {
    'User-Agent': USER_AGENT,
    Referer: normalizeBaseUrl(state.config.siteBase) + '/',
    Origin: normalizeBaseUrl(state.config.siteBase),
    'Accept-Language': 'zh-CN,zh;q=0.9'
  };
}

function parseExtend(input) {
  if (!input) return {};
  if (typeof input === 'object') return input.ext ? parseExtend(input.ext) : input;
  const text = String(input).trim();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch (_) {
    return {};
  }
}

function normalizeConfig(input) {
  const config = { ...DEFAULT_CONFIG, ...(input || {}) };
  config.siteBase = normalizeBaseUrl(config.siteBase || DEFAULT_CONFIG.siteBase);
  config.timeoutMs = clampNumber(config.timeoutMs, DEFAULT_CONFIG.timeoutMs, 3000, 60000);
  config.categories = Array.isArray(config.categories) && config.categories.length
    ? config.categories : DEFAULT_CONFIG.categories;
  config.filters = config.filters && typeof config.filters === 'object' && !Array.isArray(config.filters)
    ? config.filters : {};
  return config;
}

function extractCards(html) {
  const starts = [];
  const marker = /<div\s+class="hg-drama-card"\s+([^>]*)>/gi;
  let match;
  while ((match = marker.exec(html)) !== null) {
    starts.push({ index: match.index, attrs: match[1] });
  }

  const result = [];
  const seen = new Set();
  for (let index = 0; index < starts.length; index++) {
    const current = starts[index];
    const fragment = html.slice(current.index, starts[index + 1] ? starts[index + 1].index : html.length);
    const id = getAttr(current.attrs, 'data-track-id') || ((fragment.match(/href="\/detail\/(\d+)\//i) || [])[1] || '');
    const title = getAttr(current.attrs, 'data-track-title') || cleanText((fragment.match(/hg-drama-card__title[^>]*>[\s\S]*?<a[^>]*>([\s\S]*?)<\/a>/i) || [])[1]);
    if (!id || !title || seen.has(id)) continue;
    seen.add(id);
    const picture = getAttr(fragment, 'data-src') || getAttr(fragment, 'src');
    const episode = cleanText((fragment.match(/class="hg-drama-card__episode"[^>]*>([\s\S]*?)<\/span>/i) || [])[1]);
    const score = cleanText((fragment.match(/class="hg-drama-card__score"[^>]*>([\s\S]*?)<\/span>/i) || [])[1]);
    result.push({ vod_id: id, vod_name: title, vod_pic: imageProxyUrl(absoluteUrl(picture)), vod_remarks: episode || score });
  }
  return result;
}

function extractEpisodes(html) {
  const episodes = [];
  const seen = new Set();
  const pattern = /<a\b([^>]*?)\bdata-ep-id="(\d+)"([^>]*)>/gi;
  let match;
  while ((match = pattern.exec(html)) !== null) {
    const number = Number(match[2]);
    const href = getAttr(match[1] + ' ' + match[3], 'href');
    if (!number || !href || seen.has(number)) continue;
    seen.add(number);
    episodes.push({ number, url: absoluteUrl(href) });
  }
  return episodes.sort((left, right) => left.number - right.number);
}

function parseInitialData(html) {
  const match = String(html || '').match(/<script\s+id="videoInitialData"\s+type="application\/json">([\s\S]*?)<\/script>/i);
  try {
    return match ? JSON.parse(match[1]) : {};
  } catch (_) {
    return {};
  }
}

function categoryPath(typeId, page) {
  return '/' + typeId + (page > 1 ? '/' + page : '') + '/';
}

function getAttr(source, name) {
  const match = String(source || '').match(new RegExp('(?:^|\\s)' + name + '="([^"]*)"', 'i'));
  return match ? decodeHtml(match[1]) : '';
}

function decodeHtml(value) {
  return String(value || '')
    .replace(/&amp;/g, '&').replace(/&quot;|&#34;/g, '"')
    .replace(/&#39;|&apos;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&#x([0-9a-f]+);/gi, (_, hex) => String.fromCharCode(parseInt(hex, 16)))
    .replace(/&#(\d+);/g, (_, code) => String.fromCharCode(parseInt(code, 10)));
}

function cleanText(value) {
  return decodeHtml(String(value || '').replace(/<[^>]*>/g, ' ')).replace(/\s+/g, ' ').trim();
}

function absoluteUrl(value) {
  const text = decodeHtml(value).trim();
  if (!text) return '';
  if (/^https?:\/\//i.test(text)) return text;
  return normalizeBaseUrl(state.config.siteBase) + (text.startsWith('/') ? text : '/' + text);
}

function imageProxyUrl(url) {
  if (!url) return '';
  if (typeof getProxy !== 'function') return url;
  return getProxy(true) + '&url=' + encodeURIComponent(url);
}

function normalizeId(ids) {
  if (Array.isArray(ids)) return String(ids[0] || '');
  return String(ids || '').split(',')[0];
}

function pagedResult(list, page, pagecount, total) {
  return {
    page,
    pagecount: Number(pagecount || 1),
    limit: list.length || 20,
    total: Number(total || 0),
    list
  };
}

function failList(error) {
  state.lastError = error.message || String(error);
  return stringify({ list: [] });
}

function failPage(error, page) {
  state.lastError = error.message || String(error);
  return stringify(pagedResult([], page, 1, 0));
}

function clampPage(value) {
  return Math.max(1, Number.parseInt(value || '1', 10) || 1);
}

function clampNumber(value, fallback, min, max) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.min(max, Math.max(min, Math.round(number))) : fallback;
}

function normalizeBaseUrl(value) {
  return String(value || '').replace(/\/+$/, '');
}

function stringify(value) {
  return JSON.stringify(value);
}

const spider = {
  init, home, homeVod, category, detail, search, play, proxy,
  homeContent, homeVideoContent, categoryContent, detailContent, searchContent, playerContent,
  destroy, setTransport, getConfig, getLastError
};

function __jsEvalReturn() {
  return spider;
}

export {
  init, home, homeVod, category, detail, search, play, proxy,
  homeContent, homeVideoContent, categoryContent, detailContent, searchContent, playerContent,
  destroy, setTransport, getConfig, getLastError, __jsEvalReturn
};

export default spider;