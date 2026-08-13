import { useEffect, useMemo, useRef, useState, type MouseEvent } from 'react'
import {
  ArrowRight,
  Check,
  ChevronLeft,
  ChevronRight,
  FileText,
  Menu,
  RotateCcw,
  Search,
  Star,
  X,
  ZoomIn,
} from 'lucide-react'
import { chapters, lessons, snippetFor, type Lesson } from './content'

const COMPLETION_KEY = 'core-study-completed-v1'
const FAVORITES_KEY = 'core-study-favorites-v1'
type Edition = 'learning' | 'source'

function readStored(key: string) {
  try {
    const value = JSON.parse(localStorage.getItem(key) ?? '[]')
    return new Set<string>(Array.isArray(value) ? value : [])
  } catch {
    return new Set<string>()
  }
}

function lessonFromUrl() {
  const id = new URLSearchParams(window.location.search).get('lesson')
  return lessons.find((lesson) => lesson.id === id)?.id ?? lessons[0].id
}

function editionFromUrl(): Edition {
  return new URLSearchParams(window.location.search).get('view') === 'source' ? 'source' : 'learning'
}

function shortTitle(lesson: Lesson) {
  return lesson.title.replace(/^\d{2}｜/, '')
}

function lessonNumber(lesson: Lesson, chapterLessons?: Lesson[]) {
  const match = lesson.title.match(/^(\d{2})｜/)
  if (match) return match[1]
  const index = chapterLessons?.findIndex((item) => item.id === lesson.id) ?? -1
  return String(index + 1).padStart(2, '0')
}

function SearchModal({ onClose, onSelect }: { onClose: () => void; onSelect: (lesson: Lesson) => void }) {
  const [query, setQuery] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const normalized = query.trim().toLocaleLowerCase('zh-CN')
  const results = useMemo(() => {
    if (!normalized) return lessons.slice(0, 8)
    return lessons
      .filter((lesson) => lesson.title.toLocaleLowerCase('zh-CN').includes(normalized) || lesson.searchable.includes(normalized))
      .slice(0, 30)
  }, [normalized])

  useEffect(() => {
    inputRef.current?.focus()
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="search-modal" role="dialog" aria-modal="true" aria-label="搜索课程">
      <button className="modal-backdrop" onClick={onClose} aria-label="关闭搜索" />
      <div className="search-panel">
        <div className="search-input-row">
          <Search size={19} />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="输入：分布式锁、MVCC、消息积压…"
          />
          <button onClick={onClose}>ESC</button>
        </div>
        <div className="search-results">
          <div className="results-label">{normalized ? `找到 ${results.length} 个匹配结果` : '从课程开头继续'}</div>
          {results.map((lesson, index) => (
            <button key={lesson.id} onClick={() => onSelect(lesson)}>
              <span className="result-number">{String(index + 1).padStart(2, '0')}</span>
              <span>
                <strong>{shortTitle(lesson)}</strong>
                <small>{lesson.chapter} · {snippetFor(lesson, query)}</small>
              </span>
              <ArrowRight size={17} />
            </button>
          ))}
          {!results.length && <div className="empty-search">没有找到相关内容，试试更短的关键词。</div>}
        </div>
      </div>
    </div>
  )
}

const discoverySteps = [
  {
    title: '先从找门店开始',
    lead: '你只知道要找“库存服务”，不知道它今天运行在哪台机器。先把注册中心想成会变化的地址簿。',
    registry: '还没有正式术语：地图里保存三家营业门店',
    client: '订单服务还没有本地名单',
    route: '尚未发起业务请求',
    change: '这一页只建立一个直觉：地址会变，因此不能永久写死。',
  },
  {
    title: '三台库存实例完成注册',
    lead: '上海、杭州、宁波三个实例把 IP、端口和区域交给注册中心，名单版本变成 18。',
    registry: 'version=18：上海、杭州、宁波均健康',
    client: '订单服务订阅后缓存同一份 version=18',
    route: '订单 → 上海（也可以选择杭州、宁波）',
    change: '正式术语现在才出现：实例注册、服务订阅、本地缓存。',
  },
  {
    title: '上海节点突然断电',
    lead: '节点来不及注销。请先预测：注册中心和订单服务保存的地址会不会在同一毫秒消失？',
    registry: '仍是 version=18；下一次心跳尚未发生',
    client: '仍是 version=18；上海还在候选名单',
    route: '下一个请求仍可能选择上海',
    change: '真实状态已经变化，观察者的状态还没变化，这就是检测与传播窗口。',
  },
  {
    title: '订单服务先遇到一次失败',
    lead: '请求选中上海并连接失败。调用方已经拿到比全局通知更近的新证据。',
    registry: '可能仍未完成三次失败确认',
    client: '把上海放入本地隔离区；名单本身仍是 version=18',
    route: '订单 ✕ 上海 → 改投杭州 ✓',
    change: '客户端先止损，不必等全局名单收敛；写请求仍需要幂等。',
  },
  {
    title: '注册中心确认并推送移除',
    lead: '连续心跳失败达到阈值后，注册中心发布 version=19。',
    registry: 'version=19：只剩杭州、宁波',
    client: '收到推送后用 version=19 替换旧名单',
    route: '订单 → 杭州或宁波',
    change: '局部止损发生在前，全局状态收敛发生在后。两者共同构成高可用。',
  },
  {
    title: '如果注册中心此刻也失联',
    lead: '已有订单服务还能用本地名单，但新节点、下线和扩容信息无法传播。',
    registry: '控制面不可达',
    client: '继续使用最后一份带版本和时间的缓存',
    route: '已有数据面暂时继续；冷启动客户端可能失败',
    change: '此时应冻结发布和伸缩，保护现有拓扑，而不是假装系统完全正常。',
  },
  {
    title: '最后再翻译 AP 与 CP',
    lead: '网络分区时，是继续返回可能陈旧的实例名单，还是拒绝部分操作以维持更强的一致视图？',
    registry: '讨论的是注册信息一致性，不是库存业务数据一致性',
    client: '偏可用方案要求缓存、换节点、版本和收敛能力',
    route: '选择取决于状态语义与错误后果，不存在无条件标准答案',
    change: '现在术语已经能映射回前六步中的具体状态，而不是悬空定义。',
  },
]

function ServiceDiscoveryWalkthrough() {
  const [step, setStep] = useState(0)
  const current = discoverySteps[step]
  return (
    <section className="walkthrough" aria-label="服务发现零基础逐步推演">
      <div className="walkthrough-head">
        <div>
          <span>零基础逐步推演</span>
          <strong>先看状态怎样变化，再读完整原理</strong>
        </div>
        <b>{step + 1} / {discoverySteps.length}</b>
      </div>
      <div className="walkthrough-progress" aria-hidden="true">
        {discoverySteps.map((_, index) => <i key={index} className={index <= step ? 'active' : ''} />)}
      </div>
      <div className="walkthrough-stage">
        <span className="walkthrough-step-label">第 {step + 1} 步</span>
        <h2>{current.title}</h2>
        <p>{current.lead}</p>
        <div className="walkthrough-state-grid">
          <div><small>注册中心现在知道什么</small><strong>{current.registry}</strong></div>
          <div><small>订单服务现在握着什么</small><strong>{current.client}</strong></div>
          <div><small>这次请求会走到哪里</small><strong>{current.route}</strong></div>
        </div>
        <aside><span>这一步只改变一件事</span>{current.change}</aside>
      </div>
      <div className="walkthrough-controls">
        <button onClick={() => setStep(0)} disabled={step === 0}><RotateCcw size={15} /> 重新开始</button>
        <span />
        <button onClick={() => setStep((value) => Math.max(0, value - 1))} disabled={step === 0}><ChevronLeft size={16} /> 上一步</button>
        <button className="primary" onClick={() => setStep((value) => Math.min(discoverySteps.length - 1, value + 1))} disabled={step === discoverySteps.length - 1}>
          {step === discoverySteps.length - 1 ? '推演完成' : '揭示下一步'} <ChevronRight size={16} />
        </button>
      </div>
    </section>
  )
}

function GenericLessonWalkthrough({ lesson }: { lesson: Lesson }) {
  const stages = ['先看具体场景', ...lesson.walkthroughFlow]
  const [step, setStep] = useState(0)
  const action = step === 0 ? '先只辨认对象和数字，不背术语' : lesson.walkthroughFlow[step - 1]
  const next = step < lesson.walkthroughFlow.length ? lesson.walkthroughFlow[step] : '到达可以核对的终态'
  const previous = step <= 1 ? '尚未执行机制动作' : lesson.walkthroughFlow[step - 2]

  return (
    <section className="walkthrough" aria-label={`${lesson.title}零基础逐步推演`}>
      <div className="walkthrough-head">
        <div>
          <span>零基础逐步推演</span>
          <strong>每次只推进一个状态，再进入长文</strong>
        </div>
        <b>{step + 1} / {stages.length}</b>
      </div>
      <div className="walkthrough-progress" style={{ gridTemplateColumns: `repeat(${stages.length}, 1fr)` }} aria-hidden="true">
        {stages.map((_, index) => <i key={index} className={index <= step ? 'active' : ''} />)}
      </div>
      <div className="walkthrough-stage">
        <span className="walkthrough-step-label">第 {step + 1} 步</span>
        <h2>{stages[step]}</h2>
        <p>{step === 0 ? lesson.walkthroughExample : `现在只执行“${action}”。先确认这一步留下的结果，再继续。`}</p>
        <div className="walkthrough-state-grid">
          <div><small>上一状态</small><strong>{previous}</strong></div>
          <div><small>当前只做这一件事</small><strong>{action}</strong></div>
          <div><small>结果交给哪里</small><strong>{next}</strong></div>
        </div>
        <aside><span>先预测，再揭晓</span>{lesson.walkthroughQuestion}</aside>
      </div>
      <div className="walkthrough-controls">
        <button onClick={() => setStep(0)} disabled={step === 0}><RotateCcw size={15} /> 重新开始</button>
        <span />
        <button onClick={() => setStep((value) => Math.max(0, value - 1))} disabled={step === 0}><ChevronLeft size={16} /> 上一步</button>
        <button className="primary" onClick={() => setStep((value) => Math.min(stages.length - 1, value + 1))} disabled={step === stages.length - 1}>
          {step === stages.length - 1 ? '推演完成' : '揭示下一步'} <ChevronRight size={16} />
        </button>
      </div>
    </section>
  )
}

function App() {
  const [currentId, setCurrentId] = useState(lessonFromUrl)
  const [edition, setEdition] = useState<Edition>(editionFromUrl)
  const [completed, setCompleted] = useState(() => readStored(COMPLETION_KEY))
  const [favorites, setFavorites] = useState(() => readStored(FAVORITES_KEY))
  const [expandedChapter, setExpandedChapter] = useState(() => lessons.find((lesson) => lesson.id === lessonFromUrl())?.chapter ?? chapters[0])
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [lightbox, setLightbox] = useState<{ src: string; alt: string } | null>(null)
  const currentIndex = Math.max(0, lessons.findIndex((lesson) => lesson.id === currentId))
  const lesson = lessons[currentIndex]
  const chapterLessons = lessons.filter((item) => item.chapter === lesson.chapter)
  const rewriteDone = lessons.filter((item) => item.rewriteComplete).length
  const chapterDone = chapterLessons.filter((item) => completed.has(item.id)).length
  const progress = Math.round((completed.size / lessons.length) * 100)
  const previous = lessons[currentIndex - 1]
  const next = lessons[currentIndex + 1]
  const pageHeadings = edition === 'learning' ? lesson.headings : lesson.sourceHeadings

  const selectLesson = (selected: Lesson) => {
    const url = new URL(window.location.href)
    url.searchParams.set('lesson', selected.id)
    url.hash = ''
    window.history.pushState({}, '', url)
    setCurrentId(selected.id)
    setExpandedChapter(selected.chapter)
    setSidebarOpen(false)
    setSearchOpen(false)
    window.scrollTo({ top: 0 })
  }

  useEffect(() => {
    const onPopState = () => {
      const id = lessonFromUrl()
      setCurrentId(id)
      setEdition(editionFromUrl())
      setExpandedChapter(lessons.find((item) => item.id === id)?.chapter ?? chapters[0])
    }
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  useEffect(() => {
    if (edition !== 'learning') return
    let active = true
    import('mermaid').then(({ default: mermaid }) => {
      if (!active) return
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: 'strict',
        theme: 'base',
        themeVariables: {
          fontFamily: 'Inter, PingFang SC, Microsoft YaHei, sans-serif',
          primaryColor: '#e8f1ff',
          primaryTextColor: '#183153',
          lineColor: '#5f7f7c',
        },
      })
      return mermaid.run({ querySelector: '.mermaid' })
    }).catch((error) => console.error('Mermaid 图示渲染失败', error))
    return () => { active = false }
  }, [currentId, edition])

  useEffect(() => {
    if (edition !== 'source' || lesson.hasSource) return
    const url = new URL(window.location.href)
    url.searchParams.delete('view')
    window.history.replaceState({}, '', url)
    setEdition('learning')
  }, [edition, lesson.hasSource])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setSearchOpen(true)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const toggleStored = (key: string, state: Set<string>, update: (value: Set<string>) => void) => {
    const nextState = new Set(state)
    nextState.has(lesson.id) ? nextState.delete(lesson.id) : nextState.add(lesson.id)
    update(nextState)
    localStorage.setItem(key, JSON.stringify(Array.from(nextState)))
  }

  const selectEdition = (nextEdition: Edition) => {
    const url = new URL(window.location.href)
    if (nextEdition === 'source') url.searchParams.set('view', 'source')
    else url.searchParams.delete('view')
    url.hash = ''
    window.history.pushState({}, '', url)
    setEdition(nextEdition)
    window.scrollTo({ top: 0 })
  }

  const onArticleClick = (event: MouseEvent<HTMLElement>) => {
    const target = event.target
    if (target instanceof HTMLImageElement) setLightbox({ src: target.src, alt: target.alt })
    if (target instanceof HTMLElement && lesson.hasSource) {
      const anchor = target.closest('a')
      if (anchor?.getAttribute('href')?.startsWith('../content/')) {
        event.preventDefault()
        selectEdition('source')
      }
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <button className="icon-button mobile-menu" onClick={() => setSidebarOpen(true)} aria-label="打开课程目录"><Menu size={19} /></button>
        <button className="brand" onClick={() => selectLesson(lessons[0])} aria-label="回到课程首页"><span>Core</span> Study</button>
        <button className="search-trigger" onClick={() => setSearchOpen(true)}>
          <Search size={18} />
          <span>搜索 50 篇学习稿、案例与机制</span>
          <kbd>⌘ K</kbd>
        </button>
        <div className="top-progress">
          <span>学习进度</span>
          <strong>{progress}%</strong>
          <div className="progress-track"><i style={{ width: `${progress}%` }} /></div>
        </div>
      </header>

      <div className="workspace">
        <aside className={`course-sidebar ${sidebarOpen ? 'is-open' : ''}`}>
          <div className="sidebar-mobile-head">
            <strong>课程目录</strong>
            <button className="icon-button" onClick={() => setSidebarOpen(false)} aria-label="关闭目录"><X size={18} /></button>
          </div>
          <div className="course-summary">
            <span className="eyebrow">核心知识学习路径</span>
            <strong>后端工程核心能力</strong>
            <small>{rewriteDone} / {lessons.length} 篇深度重写完成 · {chapters.length} 个专题</small>
          </div>
          <nav aria-label="课程章节">
            {chapters.map((chapter) => {
              const items = lessons.filter((item) => item.chapter === chapter)
              const expanded = chapter === expandedChapter
              return (
                <section className="topic-group" key={chapter}>
                  <button className={`topic-button ${expanded ? 'active' : ''}`} onClick={() => setExpandedChapter(expanded ? '' : chapter)}>
                    <span>{chapter}</span><small>{items.length}</small>
                  </button>
                  {expanded && (
                    <div className="lesson-list">
                      {items.map((item) => (
                        <button className={`lesson-link ${item.id === lesson.id ? 'active' : ''}`} key={item.id} onClick={() => selectLesson(item)}>
                          <i className={completed.has(item.id) ? 'done' : ''}>{completed.has(item.id) ? '✓' : lessonNumber(item, items)}</i>
                          <span>{shortTitle(item)}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </section>
              )
            })}
          </nav>
        </aside>
        {sidebarOpen && <button className="scrim" aria-label="关闭目录" onClick={() => setSidebarOpen(false)} />}

        <main className="reader">
          <div className="reader-meta">
            <span>{lesson.chapter}</span>
            <b>第 {currentIndex + 1} 篇</b>
            <span>{edition === 'learning' ? (lesson.rewriteComplete ? '深度重写完成' : '旧版草稿 · 待重写') : `来源层 · ${lesson.sourcePages} 页`}</span>
          </div>
          <div className="lesson-actions">
            {lesson.hasSource && (
              <button className={edition === 'source' ? 'is-source' : ''} onClick={() => selectEdition(edition === 'learning' ? 'source' : 'learning')}>
                <FileText size={14} /> {edition === 'learning' ? '查看来源稿' : '返回学习稿'}
              </button>
            )}
            <button className={favorites.has(lesson.id) ? 'is-favorite' : ''} onClick={() => toggleStored(FAVORITES_KEY, favorites, setFavorites)}>
              <Star size={14} /> {favorites.has(lesson.id) ? '已收藏' : '收藏'}
            </button>
            <button className={completed.has(lesson.id) ? 'is-complete' : ''} onClick={() => toggleStored(COMPLETION_KEY, completed, setCompleted)}>
              <Check size={15} /> {completed.has(lesson.id) ? '已完成' : '标记完成'}
            </button>
          </div>

          {edition === 'source' && (
            <section className="source-layer-note">
              <strong>当前是来源层</strong>
              <span>用于交叉核对资料范围，可能保留原始页面与旧表达；默认学习内容请切回独立学习版。</span>
            </section>
          )}

          {edition === 'learning' && !lesson.rewriteComplete && (
            <section className="rewrite-status-note">
              <strong>本节仍是旧版草稿</strong>
              <span>保留它是为了不丢失现有工程内容；它尚未按第 01 节的连续推导、完整边界和工程验证标准重写，因此不计入已交付章节。</span>
            </section>
          )}

          {edition === 'learning' && lesson.id === '01-service-discovery' && <ServiceDiscoveryWalkthrough />}
          {edition === 'learning' && lesson.id !== '01-service-discovery' && lesson.walkthroughFlow.length > 0 && <GenericLessonWalkthrough key={lesson.id} lesson={lesson} />}

          <article
            className={`markdown-body ${edition === 'source' ? 'source-edition' : 'learning-edition'}`}
            onClick={onArticleClick}
            dangerouslySetInnerHTML={{ __html: edition === 'learning' ? lesson.learningHtml : lesson.sourceHtml }}
          />

          <nav className="lesson-pagination" aria-label="前后课程">
            <button disabled={!previous} onClick={() => previous && selectLesson(previous)}>
              <small>上一节</small><span>{previous ? shortTitle(previous) : '已经是第一节'}</span>
            </button>
            <button disabled={!next} onClick={() => next && selectLesson(next)}>
              <small>下一节 <ArrowRight size={14} /></small><span>{next ? shortTitle(next) : '已经学完全部课程'}</span>
            </button>
          </nav>
        </main>

        <aside className="page-toc">
          <span className="eyebrow">本页目录</span>
          <nav>
            {pageHeadings.slice(0, 14).map((heading) => (
              <a key={heading.id} className={heading.level === 3 ? 'sub' : ''} href={`#${heading.id}`}>{heading.label}</a>
            ))}
          </nav>
          <div className="topic-progress-card">
            <span>专题进度</span>
            <strong>{lesson.chapter}</strong>
            <small>{chapterDone} / {chapterLessons.length} 篇已完成</small>
            <div className="progress-track"><i style={{ width: `${chapterLessons.length ? chapterDone / chapterLessons.length * 100 : 0}%` }} /></div>
          </div>
          {lesson.hasSource && (
            <button className="source-card" onClick={() => selectEdition(edition === 'learning' ? 'source' : 'learning')}>
              <FileText size={16} /><span>{edition === 'learning' ? `来源资料 ${lesson.sourcePages} 页` : '返回独立学习稿'}</span>
            </button>
          )}
        </aside>
      </div>

      {searchOpen && <SearchModal onClose={() => setSearchOpen(false)} onSelect={selectLesson} />}

      {lightbox && (
        <div className="image-lightbox" role="dialog" aria-modal="true" aria-label="查看来源图片">
          <button className="image-backdrop" onClick={() => setLightbox(null)} aria-label="关闭原图" />
          <div className="image-lightbox-panel">
            <header><span><ZoomIn size={16} /> 来源图片</span><button onClick={() => setLightbox(null)}>关闭</button></header>
            <div><img src={lightbox.src} alt={lightbox.alt} /></div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
