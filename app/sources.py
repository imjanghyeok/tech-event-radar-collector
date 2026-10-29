"""Source catalog, public-list collectors and optional search API discovery."""
import asyncio
import json
import os
import re
from dataclasses import dataclass, asdict
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup
from .core import new_event, canonical, categories, activity_type, iso_now
from .importers import parse_dev_event
from .collector import DEV_EVENT_URL, json_nodes

@dataclass(frozen=True)
class Source:
    id: str
    name: str
    group: str
    url: str
    pattern: str
    dynamic: bool = False
    keyword: bool = False
    search_only: bool = False
    club: bool = False

SOURCES = [
    Source('club_yapp','YAPP','동아리·연합 커뮤니티','https://www.yapp.co.kr/',r'(?:www\.)?yapp\.co\.kr/.*',club=True),
    Source('club_depromeet','디프만','동아리·연합 커뮤니티','https://www.depromeet.com/recruit',r'(?:www\.)?depromeet\.com/.*',club=True),
    Source('club_sopt','SOPT','동아리·연합 커뮤니티','https://recruit.sopt.org/',r'(?:recruit\.)?sopt\.org/.*',True,club=True),
    Source('club_dnd','DND','동아리·연합 커뮤니티','https://dnd.ac/',r'dnd\.ac/.*',club=True),
    Source('club_nexters','넥스터즈','동아리·연합 커뮤니티','https://nexters.co.kr/',r'nexters\.co\.kr/.*',club=True),
    Source('club_prography','프로그라피','동아리·연합 커뮤니티','https://prography.org/',r'prography\.org/.*',club=True),
    Source('club_mashup','Mash-Up','동아리·연합 커뮤니티','https://recruit.mash-up.kr/',r'(?:recruit\.)?mash-up\.kr/.*',True,club=True),
    Source('club_cotato','코테이토','동아리·연합 커뮤니티','https://recruit.cotato.kr/',r'(?:recruit\.)?cotato\.kr/.*',True,club=True),
    Source('club_ausg','AUSG','동아리·연합 커뮤니티','https://ausg.me/',r'ausg\.me/.*',club=True),
    Source('club_sipe','SIPE','동아리·연합 커뮤니티','https://sipe.team/',r'sipe\.team/.*',True,club=True),
    Source('club_cloudclub','Cloud Club','동아리·연합 커뮤니티','https://cloudclub.kr/',r'cloudclub\.kr/.*',club=True),
    Source('dev_event','Dev-Event','행사 플랫폼',DEV_EVENT_URL,''),
    Source('eventus','이벤터스 · IT','행사 플랫폼','https://event-us.kr/search?keyword=개발자',r'event-us\.kr/[^/?]+/event/\d+',True),
    Source('onoffmix','온오프믹스 · IT','행사 플랫폼','https://onoffmix.com/event/main',r'onoffmix\.com/event/\d+',True,True),
    Source('luma','Luma · Seoul','행사 플랫폼','https://luma.com/seoul',r'luma\.com/[a-zA-Z0-9-]+$',True,True),
    Source('meetup','AWSKRUG Meetup','개발자 커뮤니티','https://www.meetup.com/awskrug/events/',r'meetup\.com/(?:ko-kr/)?[^/]+/events/\d+',True),
    Source('ticketa','Ticketaco','행사 플랫폼','https://ticketa.co/',r'ticketa\.co/(?:en/)?event/[a-zA-Z0-9]+',True,True),
    Source('partiful','Partiful','행사 플랫폼','https://partiful.com/',r'partiful\.com/e/[a-zA-Z0-9]+',True,True),
    Source('okky','OKKY 모임·스터디','스터디·프로젝트','https://okky.kr/community/gathering',r'okky\.kr/articles/\d+'),
    Source('inflearn_projects','인프런 프로젝트','스터디·프로젝트','https://www.inflearn.com/community/projects',r'inflearn\.com/projects/\d+'),
    Source('inflearn_studies','인프런 스터디','스터디·프로젝트','https://www.inflearn.com/community/studies',r'inflearn\.com/studies/\d+'),
    Source('hola','HOLA','스터디·프로젝트','https://holaworld.io/',r'holaworld\.io/study/[a-fA-F0-9]+',True),
    Source('letspl','렛플','스터디·프로젝트','https://letspl.me/project',r'letspl\.me/project/\d+',True),
    Source('teampik','TeamPIK','스터디·프로젝트','https://www.team-pik.com/',r'(?:teampik\.com|team-pik\.com)/(?:team|project|recruit)/[^/?]+',True),
    Source('disquiet','Disquiet','스터디·프로젝트','https://disquiet.io/',r'disquiet\.io/(?:post|product)/[^/?]+',True,True),
    Source('linkareer','링커리어 IT 대외활동','커리어·대회','https://linkareer.com/list/activity',r'linkareer\.com/activity/\d+',True,True),
    Source('dacon','DACON','해커톤·공모전','https://dacon.io/competitions',r'dacon\.io/competitions/(?:official|open)/\d+/overview'),
    Source('daker','DAKER','해커톤·공모전','https://daker.ai/public/hackathons',r'daker\.ai/public/hackathons/[a-zA-Z0-9-]+',True),
    Source('aifactory','AI Factory','해커톤·공모전','https://aifactory.space/competition',r'aifactory\.space/(?:competition|task)/\d+',True),
    Source('hackon','HACK:ON','해커톤·공모전','https://hackon.kr/',r'hackon\.kr/e/[a-zA-Z0-9]+',True),
    Source('lablab','lablab.ai','해커톤·공모전','https://lablab.ai/ai-hackathons',r'lablab\.ai/ai-hackathons/[a-zA-Z0-9-]+'),
    Source('devpost','Devpost','해커톤·공모전','https://devpost.com/hackathons',r'(?:[a-zA-Z0-9-]+\.devpost\.com|devpost\.com/hackathons/[^/?]+)',True,True),
    Source('devkorea','Dev Korea','개발자 커뮤니티','https://dev-korea.com/events',r'dev-korea\.com/events/[^/?]+'),
    Source('gdg','GDG Korea','개발자 커뮤니티','https://gdg.community.dev/',r'gdg\.community\.dev/events/details/[^/?]+',True,True),
    Source('pytorch','PyTorch Korea','개발자 커뮤니티','https://discuss.pytorch.kr/latest.json',r'discuss\.pytorch\.kr/t/[^/?]+/\d+',False,True),
    Source('openinfra','OpenInfra Korea','개발자 커뮤니티','https://www.meetup.com/openstack-and-open-infrastructure-korea/',r'meetup\.com/(?:ko-kr/)?[^/]+/events/\d+',True),
    Source('cncf','CNCF Events','개발자 커뮤니티','https://www.cncf.io/events/',r'cncf\.io/(?:events|kubecon-cloudnativecon-events)/[^/?]+|community\.cncf\.io/events/details/[^/?]+|events\.linuxfoundation\.org/[^/?]+'),
    Source('pycon','PyCon Korea','개발자 커뮤니티','https://pycon.kr/',r'pycon\.kr/[^/?]*(?:program|ticket|registration)[^/?]*',True),
    Source('aws','AWS Korea','기업 공식','https://aws.amazon.com/ko/events/',r'(?:aws\.amazon\.com|aws-experience\.com)/[^?#]*(?:event|summit|workshop)[^?#]*',False,True),
    Source('google','Google Developers','기업 공식','https://developers.google.com/events',r'developers\.google\.com/events/[^/?]+|gdg\.community\.dev/events/details/[^/?]+|(?:rsvp|cloudonair)\.withgoogle\.com/events/[^/?]+|cloud\.google\.com/events/[^/?]+|developer\.android\.com/events/[^/?]+'),
    Source('microsoft','Microsoft Events','기업 공식','https://events.microsoft.com/',r'events\.microsoft\.com/event/[^?#]+',True,True),
    Source('nvidia','NVIDIA Korea','기업 공식','https://www.nvidia.com/ko-kr/events/',r'nvidia\.com/[^?#]*(?:event|ai-day|gtc)[^?#]+',False,True),
    Source('mongodb','MongoDB Events','기업 공식','https://www.mongodb.com/events',r'mongodb\.com/(?:events|local)/[^/?]+'),
    Source('redis','Redis Events','기업 공식','https://redis.io/events/',r'redis\.io/(?:events|resources/webinars|resources/videos)/[^/?]+'),
    Source('redhat','Red Hat Korea','기업 공식','https://www.redhat.com/ko/events',r'redhat\.com/(?:ko|en)/(?:events|engage)/[^/?]+'),
    Source('oracle','Oracle Korea','기업 공식','https://www.oracle.com/kr/events/',r'oracle\.com/[^?#]*(?:event|webinar)[^?#]+',False,True),
    Source('jetbrains','JetBrains Events','기업 공식','https://www.jetbrains.com/company/conferences/',r'(?:jetbrains\.com|lp\.jetbrains\.com)/[^?#]*(?:event|day|conference|webinar)[^?#]*'),
    Source('openai','OpenAI Events','기업 공식','https://events.openai.com/',r'events\.openai\.com/[^/?]+',True),
    Source('meta','Meta Developers','기업 공식','https://dev.meta.ai/events',r'(?:developers\.facebook\.com|dev\.meta\.ai)/events/[^/?]+',True,search_only=True),
    Source('wanted','원티드 이벤트','커리어·대회','https://www.wanted.co.kr/events',r'(?:wanted\.co\.kr/events/[^/?]+|event\.wanted\.co\.kr/[^/?]+)',True,True),
    Source('programmers','프로그래머스','커리어·대회','https://programmers.co.kr/competitions',r'(?:career\.)?programmers\.co\.kr/competitions/\d+',True),
    Source('github_spring','GitHub · Spring Plugin','OSS','https://api.github.com/search/issues?q=repo%3Aexplyt%2Fspring-plugin+is%3Aissue+is%3Aopen+no%3Aassignee&per_page=6&sort=updated',r'github\.com/explyt/spring-plugin/issues/\d+'),
    Source('github_airflow','GitHub · Apache Airflow','OSS','https://api.github.com/search/issues?q=repo%3Aapache%2Fairflow+is%3Aissue+is%3Aopen+no%3Aassignee+label%3A%22good+first+issue%22&per_page=6&sort=updated',r'github\.com/apache/airflow/issues/\d+'),
    Source('jumpit','점핏 공개 행사','커리어·대회','https://jumpit.saramin.co.kr/',r'jumpit\.saramin\.co\.kr/(?:event|education)/[^/?]+',search_only=True),
    Source('rocketpunch','로켓펀치 공개 행사','커리어·대회','https://www.rocketpunch.com/',r'rocketpunch\.com/(?:events|event)/[^/?]+',search_only=True),
    Source('linkedin','LinkedIn 공개 행사','커리어·대회','https://www.linkedin.com/',r'linkedin\.com/events/[^/?]+',search_only=True),
    Source('government','정부·공공기관 공모전','해커톤·공모전','https://www.k-startup.go.kr/',r'[a-z0-9.-]+\.go\.kr/.+',search_only=True),
    Source('university','KAIST 전산학부 공개 세미나','대학 공개행사','https://cs.kaist.ac.kr/colloquium/',r'cs\.kaist\.ac\.kr/(?:colloquium|board/view).*'),
]

TECH = re.compile(r'개발|테크|(?<![A-Za-z])AI(?![A-Za-z])|GenAI|LLM|데이터|클라우드|백엔드|해커톤|스터디|소프트웨어|보안|코딩|프로그래|GitHub|AWS|Cloud|DevOps|Python|Spring|(?<![A-Za-z])RAG(?![A-Za-z])|OSS',re.I)

def catalog():
    return [asdict(s) for s in SOURCES]

def source_match(url,source):
    parsed=urlsplit(url)
    host=(parsed.hostname or '').removeprefix('www.')
    return bool(re.match('^(?:'+source.pattern+')',host+parsed.path,re.I)) if source.pattern else False

def extract_links(html, base_url, source):
    soup=BeautifulSoup(html,'html.parser')
    found={}
    for a in soup.select('a[href]'):
        href=urljoin(base_url,a['href'])
        heading=a.select_one('h1,h2,h3,h4,[class*="title"],[data-testid*="title"]')
        lines=[x for x in a.get_text('\n',strip=True).splitlines() if x not in ('모집중','모집완료','무료','유료')]
        title=heading.get_text(' ',strip=True) if heading else (lines[0] if lines else a.get('title') or '')
        if re.fullmatch(r'Register(?: now)?|Learn more|Read more|Details|등록하기|자세히 보기',title,re.I):
            parent=a.parent
            for _ in range(4):
                if parent is None:break
                heading=parent.select_one('h2,h3,h4')
                if heading:
                    title=heading.get_text(' ',strip=True)
                    break
                parent=parent.parent
            else:title=urlsplit(href).path.strip('/').split('/')[-1].replace('-',' ')
        if not source_match(href,source) or len(title)<4:
            continue
        if source.keyword and not TECH.search(title):
            continue
        try:
            url=canonical(href)
            if source.url and url==canonical(source.url):continue
            if re.fullmatch(r'Events?|View all events|See all events|Browse events|모든 이벤트|행사 목록|이벤트|행사',title,re.I):continue
            title=re.sub(r'^(모집중|모집완료)\s*','',title)[:180]
            e=new_event(url,title,provenance=source.id,evidence=source.name+' 공개 목록에서 발견. 개별 접수 상태 검증 전.')
            e['activity_type']='oss_issue' if '/issues/' in url else activity_type(title)
            if '/projects/' in url or source.id=='letspl':e['activity_type']='project'
            if '/studies/' in url:e['activity_type']='study'
            if source.id in ('dacon','daker','aifactory','hackon','devpost','lablab'):e['activity_type']='hackathon'
            found[url]=e
        except ValueError:
            pass
    # Links in SSR JSON are source records, never executed JavaScript.
    for script in soup.select('script#__NEXT_DATA__,script[type="application/ld+json"]'):
        try:
            nodes=json_nodes(json.loads(script.string or script.get_text()))
            for n in nodes:
                title=n.get('title') or n.get('name') or n.get('projectName')
                href=n.get('url') or n.get('link')
                if isinstance(title,str) and isinstance(href,str):
                    extra=extract_anchor(title,href,base_url,source)
                    if extra: found.setdefault(extra['canonical_url'],extra)
        except (ValueError,TypeError,RecursionError):pass
    return list(found.values())[:35]

def extract_anchor(title,href,base,source):
    from html import escape
    if not source_match(urljoin(base,href),source):return None
    if source.url and canonical(urljoin(base,href))==canonical(source.url):return None
    if source.keyword and not TECH.search(title):return None
    try:return new_event(urljoin(base,href),title[:180],provenance=source.id)
    except ValueError:return None

async def discover(fetcher, renderer, record, selected=None):
    sem=asyncio.Semaphore(4)
    dynamic_sem=asyncio.Semaphore(1)
    async def one(s):
        async with sem:
            result={'id':s.id,'name':s.name,'group':s.group,'url':s.url,'count':0,'method':'http','state':'running','error':None}
            try:
                if not s.url:
                    result.update(state='missing',method='none',error='구체적인 공개 목록 URL이 없는 탐색 범주입니다. 수집 소스 설정이 필요합니다.')
                    record(result)
                    return result
                r=await fetcher.page(s.url)
                r.raise_for_status()
                if s.id.startswith('github_'):
                    items=[new_event(i['html_url'],i['title'],activity_type='oss_issue',summary=(i.get('body') or '')[:700],provenance=s.id) for i in r.json().get('items',[]) if not i.get('pull_request')]
                elif s.id=='pytorch':
                    topics=r.json().get('topic_list',{}).get('topics',[])
                    items=[new_event(f'https://discuss.pytorch.kr/t/{t["slug"]}/{t["id"]}',t['title'],provenance=s.id)
                           for t in topics if re.search(r'밋업|모임|행사|컨퍼런스|PyTorch Day|워크숍|스터디',t['title'],re.I)]
                elif s.club:
                    items=club_candidates(r.text,str(r.url),s)
                else:
                    items=parse_dev_event(r.text) if s.id=='dev_event' else extract_links(r.text,str(r.url),s)
                if not items and renderer and (s.dynamic or 'html' in r.headers.get('content-type','')):
                    async with dynamic_sem:
                        rendered=await renderer.render(s.url)
                    items=club_candidates(rendered['html'],rendered['url'],s) if s.club else extract_links(rendered['html'],rendered['url'],s)
                    result['method']='browser'
                result['count']=len(items)
                result['state']='ok' if items else 'empty'
                if not items:result['error']='공개 목록에서 후보를 추출하지 못했습니다. 형식 변경·지역 목록·로그인 여부 확인 필요.'
                for e in items:yield_items.append(e)
            except Exception as exc:
                message=str(exc) or type(exc).__name__
                status=getattr(getattr(exc,'response',None),'status_code',None)
                blocked='robots' in message or status in (401,403,429) or 'CERTIFICATE_VERIFY_FAILED' in message
                if status==404:message='등록한 공개 목록 주소가 없어졌습니다(HTTP 404). 공식 대체 주소 확인이 필요합니다.'
                elif status in (401,403,429):message=f'사이트가 자동 접근을 제한했습니다(HTTP {status}). 로그인·차단을 우회하지 않습니다.'
                elif 'certificate has expired' in message:message='공식 사이트의 TLS 인증서가 만료됐습니다. 사이트 운영자 조치가 필요합니다.'
                result.update(state='blocked' if blocked else 'error',error=message[:300])
            result['checked_at']=iso_now()
            record(result)
            return result
    yield_items=[]
    results=await asyncio.gather(*(one(s) for s in SOURCES if selected is None or s.id in selected))
    return yield_items,results


def club_candidates(html, url, source):
    """A recruitment watch page is a candidate, never proof that intake is open."""
    soup=BeautifulSoup(html,'html.parser')
    for node in soup.select('script,style,noscript'):node.decompose()
    text=soup.get_text(' ',strip=True)
    if len(text)<80 or not re.search(r'모집|지원|동아리|커뮤니티|recruit|join',text,re.I):return []
    e=new_event(source.url,source.name+' · 동아리 모집 안내',activity_type='club',
                source=source.name,organizer=source.name,summary='공식 동아리·커뮤니티 모집 안내 페이지입니다. 현재 기수·모집 기간·참가 조건은 원문 검증 결과를 확인하세요.',
                provenance=source.id,evidence='공식 안내 페이지 발견. 알림 신청과 실제 모집은 구분하며, 모집 중으로 추정하지 않습니다.')
    return [e]

def search_queries():
    from .core import now
    period=now().strftime('%Y년 %m월')
    return [
        f'{period} 개발자 행사 밋업 컨퍼런스 모집 site:event-us.kr',
        f'{period} AI 개발자 서울 site:luma.com OR site:meetup.com OR site:ticketa.co OR site:partiful.com',
        f'{period} 백엔드 프로젝트 모집 site:inflearn.com/projects OR site:okky.kr/articles OR site:letspl.me/project',
        f'{period} 개발 스터디 모집 site:holaworld.io OR site:teampik.com OR site:disquiet.io',
        f'{period} 해커톤 공모전 접수 site:dacon.io OR site:daker.ai OR site:aifactory.space OR site:hackon.kr',
        f'{period} AI hackathon registration site:lablab.ai OR site:devpost.com',
        f'{period} 개발자 행사 GDG AWSKRUG PyTorchKR OpenInfra CNCF PyCon',
        f'{period} Korea developer event AWS Google Microsoft NVIDIA MongoDB Redis RedHat Oracle JetBrains OpenAI Meta',
        f'{period} 개발자 멘토링 행사 site:wanted.co.kr OR site:programmers.co.kr OR site:jumpit.saramin.co.kr OR site:rocketpunch.com',
        f'{period} 개발자 행사 site:linkedin.com/events',
        f'{period} 소프트웨어 AI 해커톤 공모전 모집 site:go.kr OR site:ac.kr',
    ]

async def discover_search_api(fetcher):
    """Optional user-owned Brave key; no credential is ever returned to the UI."""
    key=os.environ.get('BRAVE_SEARCH_API_KEY')
    if not key:return [],{'state':'agent_bridge','message':'검색은 연결된 Codex 자동 탐색에서 수행합니다. Brave 키는 선택 사항입니다.'}
    items={}
    for query in search_queries()[:6]:
        response=await fetcher.client.get('https://api.search.brave.com/res/v1/web/search',headers={'X-Subscription-Token':key},params={'q':query,'count':10})
        response.raise_for_status()
        for r in response.json().get('web',{}).get('results',[]):
            url=r.get('url','')
            for s in SOURCES:
                if source_match(url,s):
                    try:items[url]=new_event(url,r.get('title','')[:180],summary=r.get('description','')[:700],provenance='web_search')
                    except ValueError:pass
                    break
        await asyncio.sleep(1)
    return list(items.values()),{'state':'ok','count':len(items)}
