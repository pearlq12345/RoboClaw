import { useCallback, useState } from 'react'
import { useI18n } from '../controllers/i18n'
import { postJson } from '../controllers/api'

export function CameraPreviewPanel({ cameras, busy }: { cameras: any[]; busy: boolean }) {
  const [previews, setPreviews] = useState<Record<number, string>>({})
  const [capturing, setCapturing] = useState(false)
  const { t } = useI18n()

  const capture = useCallback(async () => {
    if (busy || capturing) return
    setCapturing(true)
    try {
      await postJson('/api/setup/previews')
      const ts = Date.now()
      const map: Record<number, string> = {}
      cameras.forEach((_: any, i: number) => {
        map[i] = `/api/setup/previews/${i}?t=${ts}`
      })
      setPreviews(map)
    } catch { /* network failure is visible via empty preview */ }
    setCapturing(false)
  }, [busy, capturing, cameras])

  return (
    <div className="bg-white border border-bd/30 rounded-lg p-5 shadow-card">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs text-tx2 uppercase tracking-wider font-medium">{t('cameras')}</h3>
        <button
          onClick={capture}
          disabled={busy || capturing}
          className="px-2.5 py-0.5 border border-ac/60 text-ac rounded text-xs hover:border-ac hover:bg-ac/10 disabled:opacity-30"
        >
          {capturing ? '...' : t('refresh')}
        </button>
      </div>
      {Object.keys(previews).length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {cameras.filter((c: any) => c.connected).map((_: any, i: number) => (
            <div key={i} className="flex-1 min-w-[200px] max-w-[400px] relative bg-white rounded-lg overflow-hidden border border-bd/30 shadow-card">
              <img
                src={previews[i] || ''}
                alt={`Camera ${i}`}
                className="w-full aspect-video object-contain bg-black"
              />
            </div>
          ))}
        </div>
      ) : (
        <div className="text-sm text-tx2">{t('noCameraFeed')}</div>
      )}
    </div>
  )
}
