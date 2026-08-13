import { marked } from 'marked'

export type Heading = { id: string; label: string; level: number }

export type Lesson = {
  id: string
  order: number
  chapter: string
  title: string
  sourcePages: number
  learningRaw: string
  sourceRaw: string
  searchable: string
  learningHtml: string
  sourceHtml: string
  headings: Heading[]
  sourceHeadings: Heading[]
  hasSource: boolean
  rewriteComplete: boolean
  walkthroughFlow: string[]
  walkthroughExample: string
  walkthroughQuestion: string
}

const learningModules = import.meta.glob('../learning/*.md', {
  eager: true,
  query: '?raw',
  import: 'default',
}) as Record<string, string>

const sourceModules = import.meta.glob('../content/*.md', {
  eager: true,
  query: '?raw',
  import: 'default',
}) as Record<string, string>

const assetModules = import.meta.glob('../content/assets/*', {
  eager: true,
  query: '?url',
  import: 'default',
}) as Record<string, string>

const assetUrls = new Map(
  Object.entries(assetModules).map(([path, url]) => [path.split('/').pop()!, url]),
)

const sourcesById = new Map(
  Object.entries(sourceModules).map(([path, raw]) => [path.split('/').pop()!.replace(/\.md$/, ''), raw]),
)

function parseFrontmatter(raw: string) {
  const match = raw.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/)
  if (!match) throw new Error('Markdown 缺少 frontmatter')
  const data: Record<string, string> = {}
  for (const line of match[1].split('\n')) {
    const separator = line.indexOf(':')
    if (separator === -1) continue
    const key = line.slice(0, separator).trim()
    const value = line.slice(separator + 1).trim().replace(/^"|"$/g, '').replace(/\\"/g, '"')
    data[key] = value
  }
  return { data, body: match[2] }
}

function prepareSourceMarkdown(markdown: string) {
  return markdown
    .replace(
      /<!-- source-page: (\d+) -->/g,
      '<div class="source-page" id="pdf-page-$1"><span>资料页</span> 第 $1 页</div>',
    )
    .replace(/\.\/assets\/([^\s)]+)/g, (_, filename: string) => assetUrls.get(filename) ?? `./assets/${filename}`)
}

function render(markdown: string, isSource = false) {
  const rendered = marked.parse(isSource ? prepareSourceMarkdown(markdown) : markdown, {
    gfm: true,
    breaks: false,
  }) as string
  const mermaidReady = rendered.replace(
    /<pre><code class="language-mermaid">([\s\S]*?)<\/code><\/pre>/g,
    '<div class="mermaid-panel" aria-label="本课机制流程图"><div class="mermaid">$1</div></div>',
  )
  const used = new Map<string, number>()
  const headings: Heading[] = []
  const html = mermaidReady.replace(/<h([23])>([\s\S]*?)<\/h\1>/g, (_, levelText: string, inner: string) => {
    const label = inner.replace(/<[^>]+>/g, '').trim()
    const base = label
      .toLocaleLowerCase('zh-CN')
      .replace(/[^\p{Letter}\p{Number}]+/gu, '-')
      .replace(/^-|-$/g, '') || 'section'
    const count = used.get(base) ?? 0
    used.set(base, count + 1)
    const id = count ? `${base}-${count + 1}` : base
    headings.push({ id, label, level: Number(levelText) })
    return `<h${levelText} id="${id}">${inner}</h${levelText}>`
  })
  return { html, headings }
}

function plainText(markdown: string) {
  return markdown
    .replace(/^---[\s\S]*?---/, '')
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/[#>*_`~\-[\]()]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

export const lessons: Lesson[] = Object.values(learningModules)
  .map((learningRaw) => {
    const { data, body } = parseFrontmatter(learningRaw)
    const sourceRaw = sourcesById.get(data.id)
    const publicBody = sourceRaw
      ? body
      : body.replace(/\[查看(?:完整)?来源稿[^\]]*\]\(\.\.\/content\/[^)]+\)/g, '来源稿保留在本地工程，不随公开站点发布')
    const sourceBody = sourceRaw ? parseFrontmatter(sourceRaw).body : ''
    const learningRendered = render(publicBody)
    const sourceRendered = sourceBody ? render(sourceBody, true) : { html: '', headings: [] }
    return {
      id: data.id,
      order: Number(data.order),
      chapter: data.chapter,
      title: data.title,
      sourcePages: Number(data.source_pages),
      learningRaw,
      sourceRaw: sourceRaw ?? '',
      searchable: plainText(learningRaw).toLocaleLowerCase('zh-CN'),
      learningHtml: learningRendered.html,
      sourceHtml: sourceRendered.html,
      headings: learningRendered.headings,
      sourceHeadings: sourceRendered.headings,
      hasSource: Boolean(sourceRaw),
      rewriteComplete: data.edition === 'independent-learning-exemplar',
      walkthroughFlow: (data.walkthrough_flow ?? '').split('|').filter(Boolean),
      walkthroughExample: data.walkthrough_example ?? '',
      walkthroughQuestion: data.walkthrough_question ?? '',
    }
  })
  .sort((a, b) => a.order - b.order)

export const chapters = Array.from(new Set(lessons.map((lesson) => lesson.chapter)))

export function snippetFor(lesson: Lesson, query: string) {
  const text = plainText(lesson.learningRaw)
  const index = text.toLocaleLowerCase('zh-CN').indexOf(query.toLocaleLowerCase('zh-CN'))
  if (index === -1) return text.slice(0, 86)
  const start = Math.max(0, index - 30)
  const end = Math.min(text.length, index + query.length + 56)
  return `${start > 0 ? '…' : ''}${text.slice(start, end)}${end < text.length ? '…' : ''}`
}
