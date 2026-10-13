import Markdown, { defaultUrlTransform, type Components } from 'react-markdown'
import rehypeKatex from 'rehype-katex'
import remarkBreaks from 'remark-breaks'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import 'katex/dist/katex.min.css'

const safeUrl = (url: string) => {
  const cleaned = defaultUrlTransform(url)
  return /^https?:\/\//i.test(cleaned) ? cleaned : ''
}

const components: Components = {
  img: ({ alt }) => (alt ? <span>{alt}</span> : null),
  a: ({ href, children }) =>
    href ? (
      <a href={href} target="_blank" rel="noopener noreferrer nofollow ugc" referrerPolicy="no-referrer">
        {children}
      </a>
    ) : (
      <span>{children}</span>
    ),
}

export default function Answer({ text }: { text: string }) {
  return (
    <Markdown
      remarkPlugins={[remarkGfm, remarkMath, remarkBreaks]}
      rehypePlugins={[rehypeKatex]}
      urlTransform={safeUrl}
      skipHtml
      components={components}
    >
      {text}
    </Markdown>
  )
}
