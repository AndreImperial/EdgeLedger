import { useEffect, useMemo, useRef } from 'react'
import { ExternalLink } from 'lucide-react'

export function TradingViewChart({ symbol, source }: { symbol: string; source?: string }) {
  const container = useRef<HTMLDivElement>(null)
  const base = symbol.split('/')[0].toUpperCase()
  const isBitunix = source?.toLowerCase().includes('bitunix') || symbol.toUpperCase().endsWith('/USDT')
  const tvSymbol = isBitunix ? `BITUNIX:${base}USDT.P` : `COINBASE:${base}USD`
  const chartUrl = useMemo(() => `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(tvSymbol)}`, [tvSymbol])

  useEffect(() => {
    const host = container.current
    if (!host) return
    host.replaceChildren()
    const widget = document.createElement('div')
    widget.className = 'tradingview-widget-container__widget'
    const script = document.createElement('script')
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js'
    script.async = true
    script.type = 'text/javascript'
    script.textContent = JSON.stringify({
      autosize: true,
      symbol: tvSymbol,
      interval: '3',
      timezone: 'Etc/UTC',
      theme: 'dark',
      style: '1',
      locale: 'en',
      backgroundColor: '#09111d',
      gridColor: 'rgba(148, 163, 184, 0.08)',
      allow_symbol_change: true,
      calendar: false,
      details: true,
      hide_side_toolbar: false,
      hide_top_toolbar: false,
      hide_legend: false,
      hide_volume: true,
      save_image: true,
      withdateranges: true,
      support_host: 'https://www.tradingview.com',
    })
    const sizeFrame = () => {
      const frame = host.querySelector('iframe')
      if (!frame) return
      const height = host.clientHeight
      frame.height = String(height)
      frame.style.setProperty('height', `${height}px`, 'important')
      frame.style.setProperty('width', '100%', 'important')
    }
    const mutationObserver = new MutationObserver(sizeFrame)
    mutationObserver.observe(host, { childList: true, subtree: true })
    const resizeObserver = new ResizeObserver(sizeFrame)
    resizeObserver.observe(host)
    script.addEventListener('load', () => window.setTimeout(sizeFrame, 100))
    host.append(widget, script)
    return () => { mutationObserver.disconnect(); resizeObserver.disconnect(); host.replaceChildren() }
  }, [tvSymbol])

  return <div className="tv-chart-shell">
    <div ref={container} className="tradingview-widget-container" aria-label={`${symbol} TradingView chart`} />
    <div className="tv-chart-foot"><span>3-minute {isBitunix ? 'Bitunix perpetual' : 'Coinbase spot'} market chart</span><a href={chartUrl} target="_blank" rel="noreferrer">Open in TradingView <ExternalLink size={13} /></a></div>
  </div>
}
