import json, threading, urllib.request, urllib.error, ssl, re, datetime, pathlib, time, collections, hashlib, os
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urldefrag
from html.parser import HTMLParser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, urlsplit
ROOT=pathlib.Path(getattr(__import__('sys'),'_MEIPASS',pathlib.Path(__file__).resolve().parent))
DATA_ROOT=pathlib.Path(os.environ.get('LOCALAPPDATA',str(pathlib.Path.home()))) / 'SEO Universal Amir Edition'
DATA_ROOT.mkdir(parents=True,exist_ok=True)
TARGET=''  # No preset website
LOCK=threading.Lock()
STATE={'running':False,'error':None,'result':None,'progress':0,'stage':'idle'}
def set_progress(percent,stage):
 with LOCK:STATE.update(progress=percent,stage=stage)

class Parse(HTMLParser):
 def __init__(self):
  super().__init__(); self.title='';self.in_title=False;self.h1=[];self.in_h1=False;self.meta={};self.canonical=None;self.images=0;self.missing_alt=0;self.jsonld=0;self.links=[];self.text_parts=[];self.suppress=0;self.headings=collections.Counter();self.article_tags=0;self.jsonld_text=[];self.in_jsonld=False;self._jsonld_buffer=[];self.paragraphs=[];self.in_p=False;self._p_buffer=[];self.outbound_links=[];self.hreflang_tags=[];self.html_lang='';self.current_a=None
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='html':self.html_lang=a.get('lang','')
  if tag=='link' and 'alternate' in a.get('rel','').lower() and a.get('hreflang'):self.hreflang_tags.append({'lang':a.get('hreflang',''),'href':a.get('href','')})
  if tag=='a' and a.get('href'):self.outbound_links.append({'href':a.get('href',''),'rel':a.get('rel',''),'target':a.get('target','')})
  if tag in ('script','style','noscript'):self.suppress+=1
  if tag in ('h2','h3'):self.headings[tag]+=1
  if tag=='article':self.article_tags+=1
  if tag=='p':self.in_p=True;self._p_buffer=[]
  if tag=='title':self.in_title=True
  if tag=='h1':self.in_h1=True;self.h1.append('')
  if tag=='meta':
   k=a.get('name') or a.get('property')
   if k:self.meta[k.lower()]=a.get('content','')
  if tag=='link' and 'canonical' in a.get('rel','').lower():self.canonical=a.get('href')
  if tag=='a' and a.get('href'):self.links.append(a['href'])
  if tag=='img':
   self.images+=1
   if not a.get('alt','').strip():self.missing_alt+=1
  if tag=='script' and a.get('type','').lower()=='application/ld+json':self.jsonld+=1;self.in_jsonld=True;self._jsonld_buffer=[]
 def handle_endtag(self,tag):
  if tag in ('script','style','noscript'):self.suppress=max(0,self.suppress-1)
  if tag=='script' and self.in_jsonld:self.jsonld_text.append(''.join(self._jsonld_buffer));self.in_jsonld=False
  if tag=='p' and self.in_p:self.paragraphs.append(' '.join(self._p_buffer));self.in_p=False
  if tag=='title':self.in_title=False
  if tag=='h1':self.in_h1=False
 def handle_data(self,data):
  if self.in_jsonld:self._jsonld_buffer.append(data)
  if self.in_p and data.strip():self._p_buffer.append(data.strip())
  if not self.suppress and data.strip():self.text_parts.append(data.strip())
  if self.in_title:self.title+=data
  if self.in_h1 and self.h1:self.h1[-1]+=data

def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':'KaprisSEOAudit/1.0 (+site-owner; low-frequency)','Accept':'text/html,application/xhtml+xml,*/*'})
 with urllib.request.urlopen(req,timeout=18) as resp:
  body=resp.read(3_000_000)
  return resp.status,resp.geturl(),dict(resp.headers),body.decode(resp.headers.get_content_charset() or 'utf-8',errors='replace')

def readability_metrics(p):
 # Structural heuristics for Persian/English text; not a Flesch grade or linguistic validation.
 paragraphs=[x.strip() for x in p.paragraphs if x.strip()]
 words=re.findall(r"[^\W_]+(?:[‌'-][^\W_]+)*",' '.join(paragraphs),re.UNICODE)
 lengths=[len(re.findall(r"[^\W_]+(?:[‌'-][^\W_]+)*",x,re.UNICODE)) for x in paragraphs]
 long_count=sum(n>80 for n in lengths)
 eligible=len(words)>=80 and len(paragraphs)>=2
 score=round(100*(1-long_count/len(paragraphs))) if eligible else None
 return {'score':score,'words':len(words),'paragraphs':len(paragraphs),'long_paragraphs':long_count,'h2':p.headings['h2'],'h3':p.headings['h3'],'note':'Sample paragraph-length heuristic; Persian Flesch reading grades are not supported. Score requires at least 80 words and 2 paragraphs.'}

def extract_schema(p):
 nodes=[];errors=[]
 def walk(obj):
  if isinstance(obj,list):
   for x in obj:walk(x)
  elif isinstance(obj,dict):
   if '@type' in obj:nodes.append(obj)
   if '@graph' in obj:walk(obj['@graph'])
 for raw in p.jsonld_text:
  try:walk(json.loads(raw))
  except (ValueError,TypeError) as e:errors.append(str(e)[:90])
 return nodes,errors

def article_metrics(p,url):
 nodes,_=extract_schema(p)
 types={str(t).lower() for n in nodes for t in (n.get('@type') if isinstance(n.get('@type'),list) else [n.get('@type')]) if t}
 article_schema=bool(types & {'article','blogposting','newsarticle'})
 # Only article-looking pages receive article scores; category/home pages are N/A.
 is_article=article_schema or p.article_tags>0 and '/mag/' in urlparse(url).path.strip('/')+'/'
 words=len(re.findall(r'[^\W_]+',' '.join(p.text_parts),re.UNICODE))
 author=any(n.get('author') for n in nodes if str(n.get('@type','')).lower() in ('article','blogposting','newsarticle'))
 published=any(n.get('datePublished') for n in nodes)
 score=round(100*sum([bool(p.title.strip()),p.headings['h2']>0,author,published])/4) if is_article else None
 return {'score':score,'is_article':is_article,'words':words,'h2':p.headings['h2'],'h3':p.headings['h3'],'images':p.images,'author_schema':author,'published_schema':published,'note':'Article-structure checks only for detected articles; not an editorial-quality or keyword-relevance score.'}

def entity_metrics(p):
 nodes,errors=extract_schema(p)
 types=sorted({str(t) for n in nodes for t in (n.get('@type') if isinstance(n.get('@type'),list) else [n.get('@type')]) if t})
 named=[n for n in nodes if n.get('name') or n.get('headline')]
 sameas=sum(len(n.get('sameAs',[])) if isinstance(n.get('sameAs'),list) else int(bool(n.get('sameAs'))) for n in nodes)
 score=round(100*sum([bool(nodes),bool(named),bool(types),not errors])/4) if p.jsonld else None
 return {'score':score,'blocks':p.jsonld,'nodes':len(nodes),'types':types[:20],'named_nodes':len(named),'sameas_links':sameas,'parse_errors':errors[:5],'note':'JSON-LD presence, parseability and basic identity checks; does not verify Wikidata, Google rich-result eligibility, or factual entity accuracy.'}

def outbound_metrics(p,url):
 host=urlparse(url).hostname
 items=[]
 for a in p.outbound_links:
  href=urljoin(url,a['href']);u=urlparse(href)
  if u.scheme not in ('http','https') or not u.hostname or u.hostname==host:continue
  rel=str(a['rel']).lower().split()
  items.append({'url':href,'nofollow':'nofollow' in rel,'sponsored':'sponsored' in rel,'ugc':'ugc' in rel,'noopener':'noopener' in rel,'target_blank':a['target']=='_blank'})
 # This is a link inventory, NOT a backlink/authority or spam score.
 return {'score':None,'outbound_count':len(items),'nofollow':sum(x['nofollow'] for x in items),'sponsored':sum(x['sponsored'] for x in items),'ugc':sum(x['ugc'] for x in items),'target_blank':sum(x['target_blank'] for x in items),'sample':items[:30], 'note':'Outgoing-link inventory only. Backlinks, domain authority and link quality are not measured; N/A is intentional.'}

def hreflang_metrics(p,url):
 import re
 tags=p.hreflang_tags
 issues=[];valid=[]
 for tag in tags:
  lang=tag['lang'].strip();dest=urljoin(url,tag['href']) if tag['href'] else ''
  ok_lang=bool(re.fullmatch(r'(?:[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{2,8})*|x-default)',lang))
  ok_url=urlparse(dest).scheme in ('http','https') and bool(urlparse(dest).hostname)
  if not ok_lang or not ok_url:issues.append({'lang':lang,'href':tag['href'],'reason':'Invalid language code or URL'})
  else:valid.append({'lang':lang,'url':dest})
 duplicates=len(valid)-len({x['lang'].lower() for x in valid})
 if duplicates:issues.append({'reason':'Duplicate language declarations','count':duplicates})
 # Absence is not an error for a single-language website.
 score=round(100*len(valid)/(len(tags)+duplicates)) if tags else None
 return {'score':score,'html_lang':p.html_lang,'tags_found':len(tags),'valid_tags':len(valid),'issues':issues,'tags':valid[:30],'note':'Tag syntax and destination URL format only; reciprocal hreflang and destination availability are not checked. No tags means N/A, not a failure.'}

def aggregate_samples(rows,key):
 items=[{'url':r['url'],**r[key]} for r in rows]
 valid=[x['score'] for x in items if isinstance(x.get('score'),int)]
 return {'score':round(sum(valid)/len(valid)) if valid else None,'pages_checked':len(items),'pages_scored':len(valid),'sample':items,'note':items[0]['note'] if items else 'No sampled pages.'}

def crawl_links(home_url, homepage):
 # Bounded, same-host, read-only audit. Unknown or inaccessible URLs are not treated as healthy.
 host=urlparse(home_url).hostname
 def norm(href,base):
  url=urldefrag(urljoin(base,href))[0]
  p=urlparse(url)
  if p.scheme not in ('http','https') or p.hostname!=host:return None
  if p.path.startswith(('/cart','/checkout','/my-account','/wp-admin','/wp-json','/feed')):return None
  if p.query:return None
  return p._replace(path=p.path or '/').geturl()
 queue=collections.deque([(home_url,homepage)])
 seen=set(); pages=[]; links=set(); outcomes={}; errors=[]; inbound=collections.Counter(); page_meta=[]
 MAX_PAGES=8;MAX_LINKS=24
 while queue and len(pages)<MAX_PAGES:
  url,source=queue.popleft()
  if url in seen:continue
  seen.add(url)
  try:
   if source is None:
    time.sleep(.15)
    status,final,_,source=fetch(url)
   else:status,final=200,url
   if status!=200:errors.append({'url':url,'status':status});continue
   parser=Parse();parser.feed(source)
   pages.append({'url':url,'links':len(parser.links)})
   page_meta.append({'url':url,'title':parser.title.strip(),'description':parser.meta.get('description','').strip(),'content_hash':hashlib.sha256(' '.join(parser.text_parts).encode('utf-8')).hexdigest(),'readability':readability_metrics(parser),'article':article_metrics(parser,url),'entity':entity_metrics(parser),'link_profile':outbound_metrics(parser,url),'hreflang':hreflang_metrics(parser,url)})
   for href in parser.links:
    dest=norm(href,final)
    if dest:
     links.add(dest)
     inbound[dest]+=1
   # Only a few same-domain pages, selected from links discovered on the homepage.
   if len(pages)==1:
    for dest in sorted(links):
     if dest!=url and len(queue)<MAX_PAGES-1:queue.append((dest,None))
  except Exception as e:errors.append({'url':url,'error':str(e)[:150]})
 # Check at most 24 links with three concurrent, read-only requests.
 # Existing crawled pages are reused rather than downloaded twice.
 def check_one(url):
  if url in seen:
   return url, ({'status':200} if any(p['url']==url for p in pages) else {'status':'unknown'})
  try:
   hops=[]
   class TrackRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
     hops.append({'status':code,'url':newurl})
     if len(hops)>5: raise urllib.error.HTTPError(req.full_url,508,'Redirect limit exceeded',headers,fp)
     return super().redirect_request(req,fp,code,msg,headers,newurl)
   opener=urllib.request.build_opener(TrackRedirects())
   req=urllib.request.Request(url,headers={'User-Agent':'KaprisSEOAudit/1.0 (site-owner; low-frequency)'})
   with opener.open(req,timeout=7) as response:
    response.read(512)
    return url,{'status':response.status,'final_url':response.geturl(),'redirect_hops':hops}
  except urllib.error.HTTPError as e:return url,{'status':e.code}
  except Exception as e:return url,{'status':'unknown','error':str(e)[:120]}
 with ThreadPoolExecutor(max_workers=3) as pool:
  jobs=[]
  for url in sorted(links)[:MAX_LINKS]:
   jobs.append(pool.submit(check_one,url))
   time.sleep(.12)
  for future in as_completed(jobs):
   url,value=future.result()
   outcomes[url]=value
 broken=[{'url':u,**v} for u,v in outcomes.items() if isinstance(v['status'],int) and v['status']>=400]
 redirects=[{'url':u,**v} for u,v in outcomes.items() if v.get('final_url') and v['final_url']!=u]
 unknown=sum(v['status']=='unknown' for v in outcomes.values())
 # A clean sample is not proof that the entire website is free of broken links.
 broken_score=round(100*(len(outcomes)-len(broken)-unknown)/len(outcomes)) if outcomes else None
 # Scores describe only the inspected sample, not whole-site SEO quality.
 sampled={p['url'] for p in pages}
 candidates=sampled-{home_url}
 linked=sum(1 for u in candidates if inbound[u]>0)
 internal_score=round(100*linked/len(candidates)) if candidates else None
 known=[v for v in outcomes.values() if isinstance(v['status'],int)]
 problematic=sum(1 for v in known if v['status']>=400 or len(v.get('redirect_hops',[]))>1)
 redirect_score=round(100*(len(known)-problematic)/len(known)) if known and not unknown else None
 chains=[{'url':u,'hops':v.get('redirect_hops',[]),'final_url':v.get('final_url')} for u,v in outcomes.items() if len(v.get('redirect_hops',[]))>1]
 return {'categories':{'broken_links':broken_score,'internal_links':internal_score,'redirects':redirect_score},'page_metadata':page_meta,'pages_crawled':len(pages),'links_discovered':len(links),'links_checked':len(outcomes),'broken':broken,'redirected':redirects,'redirect_chains':chains,'internal_link_sample':{'eligible_pages':len(candidates),'pages_with_inbound_links':linked},'unknown':unknown,'errors':errors,'page_sample':pages,'limits':{'max_pages':MAX_PAGES,'max_links':MAX_LINKS},'note':'Sample-based scores only. A single-hop redirect is not penalized; orphan pages outside the crawl are unknown.'}

def audit_llms(target):
 files=[]
 for path in ('llms.txt','llms-full.txt'):
  url=urljoin(target,'/'+path)
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'KaprisSEOAudit/1.0','Accept':'text/plain'})
   with urllib.request.urlopen(req,timeout=5) as resp:
    body=resp.read(150_000).decode('utf-8',errors='replace')
    content_type=resp.headers.get('Content-Type','')
    valid=(resp.status==200 and 'html' not in content_type.lower() and bool(body.strip()) and not body.lstrip().lower().startswith('<!doctype'))
    files.append({'url':url,'status':resp.status,'valid':valid,'bytes':len(body.encode('utf-8'))})
  except urllib.error.HTTPError as e:files.append({'url':url,'status':e.code,'valid':False})
  except Exception as e:files.append({'url':url,'status':'unknown','valid':False,'error':str(e)[:100]})
 primary=files[0]
 score=100 if primary['valid'] else (0 if primary['status'] in (404,410) else None)
 return {'score':score,'files':files,'note':'Optional llms.txt discoverability check, not a Google ranking factor.'}

def _pagespeed_key():
 # Prefer the local file over a potentially stale Windows environment variable.
 path=DATA_ROOT/'pagespeed-api-key.txt'
 if path.is_file():
  try:
   key=path.read_text(encoding='utf-8-sig').strip().strip('\"\'')
   if key:return key,'file'
  except (OSError,UnicodeError):pass
 key=os.environ.get('KAPRIS_PAGESPEED_API_KEY','').strip()
 return key,('environment' if key else 'missing')

def _pagespeed_error(error,has_key):
 status=getattr(error,'code',None)
 message=''; reason=''; google_status=''
 try:
  raw=error.read(16384).decode('utf-8',errors='replace')
  parsed=json.loads(raw)
  info=parsed.get('error',{})
  message=str(info.get('message',''))[:500]
  status=info.get('code',status)
  google_status=str(info.get('status',''))[:100]
  details=info.get('details',[])
  for detail in details if isinstance(details,list) else []:
   if not isinstance(detail,dict):continue
   reason=str(detail.get('reason','') or detail.get('metadata',{}).get('reason',''))[:120]
   if reason:break
  if not reason:
   for item in info.get('errors',[]):
    if isinstance(item,dict) and item.get('reason'):
     reason=str(item['reason'])[:120];break
 except (ValueError,UnicodeError,AttributeError,OSError,TypeError):pass
 if status in (401,403):
  guidance=('Review the Google error reason and API key restrictions. If API Explorer works but this fails, check that the key is permitted for PageSpeed Insights API.' if has_key else 'Add a PageSpeed Insights API key to pagespeed-api-key.txt.')
 elif status==429:guidance='Rate limit or quota reached; try again later.'
 elif status is not None:guidance='Check the Google API response and Cloud settings.'
 else:guidance='Network or API request failed.'
 return {'score':None,'error':('HTTP '+str(status)+': ' if status is not None else '')+(message or str(error)[:200]),'http_status':status,'google_status':google_status,'google_reason':reason,'guidance':guidance}

def audit_pagespeed(target, supplied_key=None):
 # Official Google PageSpeed Insights API only. Never fabricate Lighthouse scores.
 from urllib.parse import urlencode
 key,key_source=(supplied_key,'dashboard') if supplied_key else _pagespeed_key()
 def one(strategy):
  params={'url':target,'strategy':strategy,'category':'performance'}
  if key:params['key']=key
  endpoint='https://www.googleapis.com/pagespeedonline/v5/runPagespeed?'+urlencode(params)
  try:
   req=urllib.request.Request(endpoint,headers={'User-Agent':'KaprisSEOAudit/2.0','Accept':'application/json'})
   with urllib.request.urlopen(req,timeout=25) as resp:data=json.load(resp)
   lr=data.get('lighthouseResult',{})
   score=lr.get('categories',{}).get('performance',{}).get('score')
   audits=lr.get('audits',{})
   metrics={k:audits.get(k,{}).get('displayValue') for k in ('largest-contentful-paint','cumulative-layout-shift','interaction-to-next-paint','total-blocking-time','first-contentful-paint')}
   if not isinstance(score,(int,float)):
    return {'score':None,'error':'API response did not contain a Lighthouse performance score.','guidance':'Check Lighthouse runtimeError and API availability.','runtime_error':lr.get('runtimeError',{}).get('message','')[:200]}
   return {'score':round(score*100),'metrics':metrics}
  except urllib.error.HTTPError as e:return _pagespeed_error(e,bool(key))
  except Exception as e:return {'score':None,'error':str(e)[:200],'guidance':'Check connectivity, timeout, and PageSpeed API availability.'}
 with ThreadPoolExecutor(max_workers=2) as pool:
  futures={mode:pool.submit(one,mode) for mode in ('mobile','desktop')}
  results={mode:f.result() for mode,f in futures.items()}
 return {'score':results['mobile']['score'],'strategies':results,'configured_api_key':bool(key),'api_key_source':key_source,'note':'Official Google Lighthouse lab scores. Mobile is the category score; unavailable scores are not fabricated. API keys are not included in the report.'}

def audit_duplicates(metadata):
 # Exact duplicate metadata/text within crawled sample only; not a full content originality test.
 fields=('title','description','content_hash')
 matches={}
 for field in fields:
  groups=collections.defaultdict(list)
  for row in metadata:
   if row.get(field):groups[row[field].strip().casefold()].append(row['url'])
  matches[field]=[urls for urls in groups.values() if len(urls)>1]
 count=len(metadata)
 affected=set()
 for groups in matches.values():
  for group in groups:affected.update(group[1:])
 score=round(100*(count-len(affected))/count) if count>=2 else None
 return {'score':score,'pages_checked':count,'duplicate_groups':matches,'affected_pages':len(affected),'note':'Exact title, meta-description and page-text duplicates within sampled pages only.'}

def audit(target, supplied_key=None):
 started=datetime.datetime.now(datetime.timezone.utc).isoformat()
 set_progress(8,'fetching')
 status,final,headers,html=fetch(target)
 set_progress(20,'analyzing')
 p=Parse();p.feed(html)
 tests=[('HTTP 200',status==200),('HTTPS',urlparse(final).scheme=='https'),('Title tag',bool(p.title.strip())),('Meta description',bool(p.meta.get('description','').strip())),('H1 heading',len([h for h in p.h1 if h.strip()])>0),('Canonical URL',bool(p.canonical)),('Open Graph title',bool(p.meta.get('og:title'))),('Open Graph description',bool(p.meta.get('og:description'))),('Structured data',p.jsonld>0),('Image alt coverage',p.images==0 or p.missing_alt==0)]
 score=round(100*sum(ok for _,ok in tests)/len(tests))
 def metric(items):return round(100*sum(bool(v) for v in items)/len(items)) if items else None
 headers_lower={k.lower():v for k,v in headers.items()}
 security_keys=['strict-transport-security','content-security-policy','x-frame-options','x-content-type-options','referrer-policy','permissions-policy']
 security=metric([bool(headers_lower.get(k,'').strip()) for k in security_keys])
 security_audit={'score':security,'url':final,'headers':[{'name':k,'present':bool(headers_lower.get(k,'').strip()),'value':headers_lower.get(k,'')} for k in security_keys],'note':'Presence check only; does not validate security policy strength or correctness.'}
 social_keys=['og:title','og:description','og:image','og:url','og:type','twitter:card']
 social=metric([bool(p.meta.get(k,'').strip()) for k in social_keys])
 onpage=metric([bool(p.title.strip()),bool(p.meta.get('description','').strip()),bool([h for h in p.h1 if h.strip()]),bool(p.canonical),p.images==0 or p.missing_alt==0])
 try:
  robots_status,_,_,robots_text=fetch(urljoin(final,'/robots.txt'))
  robots_score=metric([robots_status==200,'user-agent:' in robots_text.lower(),'sitemap:' in robots_text.lower()])
 except Exception:robots_score=None
 categories={'security':security,'social':social,'robots':robots_score,'onpage':onpage}
 set_progress(35,'crawling')
 link_audit=crawl_links(final,html)
 set_progress(70,'external')
 categories.update(link_audit['categories'])
 # Parallel bounded external checks; reuse existing crawled-page metadata.
 with ThreadPoolExecutor(max_workers=2) as pool:
  llms_future=pool.submit(audit_llms,target)
  psi_future=pool.submit(audit_pagespeed,target,supplied_key)
  duplicate_audit=audit_duplicates(link_audit.get('page_metadata',[]))
  llms_audit=llms_future.result()
  pagespeed_audit=psi_future.result()
 set_progress(88,'scoring')
 categories.update({'llms_txt':llms_audit['score'],'pagespeed':pagespeed_audit['score'],'duplicate_content':duplicate_audit['score']})
 readability_audit=aggregate_samples(link_audit.get('page_metadata',[]),'readability')
 article_audit=aggregate_samples(link_audit.get('page_metadata',[]),'article')
 entity_audit=aggregate_samples(link_audit.get('page_metadata',[]),'entity')
 categories.update({'readability':readability_audit['score'],'article':article_audit['score'],'entity':entity_audit['score']})
 profile_rows=[{'url':x['url'],**x['link_profile']} for x in link_audit.get('page_metadata',[])]
 link_profile_audit={'score':None,'pages_checked':len(profile_rows),'outbound_links':sum(x['outbound_count'] for x in profile_rows),'nofollow':sum(x['nofollow'] for x in profile_rows),'sponsored':sum(x['sponsored'] for x in profile_rows),'ugc':sum(x['ugc'] for x in profile_rows),'sample':profile_rows,'note':'Outgoing-link inventory across sampled pages. Backlink profile cannot be scored without external backlink data.'}
 hreflang_rows=[{'url':x['url'],**x['hreflang']} for x in link_audit.get('page_metadata',[])]
 tagged=[x for x in hreflang_rows if x['tags_found']]
 hreflang_audit={'score':round(sum(x['score'] for x in tagged)/len(tagged)) if tagged else None,'pages_checked':len(hreflang_rows),'tags_found':sum(x['tags_found'] for x in hreflang_rows),'issues_found':sum(len(x['issues']) for x in hreflang_rows),'sample':hreflang_rows,'note':'Basic hreflang syntax checks only; no tags is expected for single-language websites and is not scored.'}
 categories.update({'link_profile':link_profile_audit['score'],'hreflang':hreflang_audit['score']})

 result={'timestamp':started,'url':target,'final_url':final,'http_status':status,'scope':'Selected URL + sampled internal links','score':score,'categories':categories,'link_audit':link_audit,'security_audit':security_audit,'llms_audit':llms_audit,'pagespeed_audit':pagespeed_audit,'duplicate_audit':duplicate_audit,'readability_audit':readability_audit,'article_audit':article_audit,'entity_audit':entity_audit,'link_profile_audit':link_profile_audit,'hreflang_audit':hreflang_audit,'checks':[{'name':name,'passed':ok} for name,ok in tests],'title':p.title.strip(),'meta_description':p.meta.get('description',''),'h1':[h.strip() for h in p.h1],'canonical':p.canonical,'images':p.images,'missing_alt':p.missing_alt,'jsonld_blocks':p.jsonld,'note':'Sample-based audit of the selected URL and some same-host links; scores are not exhaustive.'}
 out=DATA_ROOT/'snapshots';out.mkdir(exist_ok=True)
 (out/(datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 (out/'latest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 return result


def parse_pagespeed_key(raw):
 # API keys (AIza...) are supported, not service-account private-key JSON.
 if not isinstance(raw,str) or len(raw)>3000:raise ValueError('Invalid PageSpeed API key input')
 raw=raw.strip()
 if not raw:return None
 if raw.startswith('{'):
  try:obj=json.loads(raw)
  except ValueError:raise ValueError('Invalid JSON: enter a Google API key or JSON with an api_key/key field')
  if not isinstance(obj,dict):raise ValueError('Expected a JSON object')
  if obj.get('type')=='service_account' or 'private_key' in obj:raise ValueError('Service-account JSON is not a PageSpeed Insights API key. Use an API key from Google Cloud Credentials.')
  raw=obj.get('api_key') or obj.get('key') or ''
 if not isinstance(raw,str) or not re.fullmatch(r'[A-Za-z0-9_\-]{20,200}',raw):raise ValueError('Enter a valid Google API key (usually starts with AIza)')
 return raw

def normalize_target(raw):
 from ipaddress import ip_address
 import socket
 if not isinstance(raw,str) or len(raw)>2048:raise ValueError('Invalid URL')
 raw=raw.strip()
 if not raw:raise ValueError('Enter a website URL')
 if '://' not in raw:raw='https://'+raw
 p=urlsplit(raw)
 if p.scheme not in ('http','https') or not p.hostname or p.username or p.password:raise ValueError('Only public HTTP/HTTPS websites are supported')
 if p.port not in (None,80,443):raise ValueError('Only standard ports are supported')
 host=p.hostname.lower()
 if host=='localhost' or host.endswith(('.local','.internal','.localhost')):raise ValueError('Local addresses are not supported')
 try:
  ip=ip_address(host)
  if not ip.is_global:raise ValueError('Private addresses are not supported')
 except ValueError as e:
  if str(e)=='Private addresses are not supported':raise
 # DNS resolution may vary; do not expose the local server to the network.
 return p._replace(fragment='',query='').geturl().rstrip('/')+'/'

def worker(target, supplied_key=None):
 try:
  result=audit(target,supplied_key)
  with LOCK:STATE.update(running=False,result=result,error=None,progress=100,stage='complete')
 except Exception as e:
  with LOCK:STATE.update(running=False,error=str(e),stage='failed')
class Handler(SimpleHTTPRequestHandler):
 def end_headers(self):
  self.send_header('Cache-Control','no-store, no-cache, must-revalidate')
  super().end_headers()
 def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT),**kwargs)
 def json(self,obj,code=200):
  b=json.dumps(obj,ensure_ascii=False).encode();self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if urlsplit(self.path).path=='/api/status':
   with LOCK: state=dict(STATE)
   if state['result'] is None and (DATA_ROOT/'snapshots/latest.json').exists():
    try:state['result']=json.loads((DATA_ROOT/'snapshots/latest.json').read_text(encoding='utf-8'))
    except (ValueError,OSError):pass
   state['version']=3
   state['target_url']=state.get('target_url') or ''
   return self.json(state)
  if self.path not in ('/','/SEO-REPORT.html'):return self.send_error(404)
  self.path='/SEO-REPORT.html';return super().do_GET()
 def do_POST(self):
  if urlsplit(self.path).path!='/api/audit':return self.send_error(404)
  if self.headers.get('Origin') not in (None,'http://127.0.0.1:8765','http://localhost:8765'):return self.json({'error':'Invalid origin'},403)
  try:
   length=int(self.headers.get('Content-Length','0'))
   if length>4096:return self.json({'error':'Request too large'},413)
   payload=json.loads(self.rfile.read(length)) if length else {}
   target=normalize_target(payload.get('url'))
   supplied_key=parse_pagespeed_key(payload.get('pagespeed_key',''))
  except (ValueError,TypeError,UnicodeDecodeError) as e:return self.json({'error':str(e)},400)
  with LOCK:
   if STATE['running']:return self.json({'error':'Audit already running'},409)
   STATE.update(running=True,error=None,result=None,target_url=target,progress=2,stage='starting')
  threading.Thread(target=worker,args=(target,supplied_key),daemon=True).start()
  return self.json({'started':True},202)
if __name__=='__main__':
 import webbrowser
 try:
  httpd=ThreadingHTTPServer(('127.0.0.1',8765),Handler)
 except OSError as e:
  print('ERROR: Cannot start SEO server on port 8765:',e,flush=True)
  print('Close any previous SEO application window and try again.',flush=True)
  raise SystemExit(1)
 print('SEO Universal running at http://127.0.0.1:8765',flush=True)
 threading.Timer(0.7,lambda:webbrowser.open('http://127.0.0.1:8765/')).start()
 try:httpd.serve_forever()
 except KeyboardInterrupt:pass
 finally:httpd.server_close()
