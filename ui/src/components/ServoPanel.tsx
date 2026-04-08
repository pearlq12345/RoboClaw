import { useCallback, useEffect, useRef, useState } from 'react'
import { useI18n } from '../controllers/i18n'
import type { SessionState } from '../controllers/dashboard'

const MOTOR_NAMES = ['shoulder_pan', 'shoulder_lift', 'elbow_flex', 'wrist_flex', 'wrist_roll', 'gripper']
const MAX_POINTS = 60
const BASE_HUES = [210, 140, 0, 270, 30, 330]

function getArmPalette(armIndex: number): string[] {
  const hue = BASE_HUES[armIndex % BASE_HUES.length]
  return MOTOR_NAMES.map((_, i) => {
    const lightness = 30 + i * 8
    return `hsl(${hue}, 70%, ${lightness}%)`
  })
}

interface ServoHistory {
  [motor: string]: number[]
}

function UnifiedServoChart({
  histories,
  armNames,
}: {
  histories: Record<string, ServoHistory>
  armNames: string[]
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const dpr = window.devicePixelRatio || 1
    const w = canvas.clientWidth
    const h = canvas.clientHeight
    canvas.width = w * dpr
    canvas.height = h * dpr
    ctx.scale(dpr, dpr)

    ctx.clearRect(0, 0, w, h)

    ctx.strokeStyle = '#e9ecf4'
    ctx.lineWidth = 0.5
    for (let y = 0; y <= h; y += h / 4) {
      ctx.beginPath()
      ctx.moveTo(0, y)
      ctx.lineTo(w, y)
      ctx.stroke()
    }

    armNames.forEach((alias, armIdx) => {
      const history = histories[alias]
      if (!history) return
      const palette = getArmPalette(armIdx)

      MOTOR_NAMES.forEach((motor, motorIdx) => {
        const data = history[motor]
        if (!data || data.length < 2) return
        ctx.strokeStyle = palette[motorIdx]
        ctx.lineWidth = 0.8
        ctx.beginPath()
        const step = w / (MAX_POINTS - 1)
        const offset = MAX_POINTS - data.length
        for (let i = 0; i < data.length; i++) {
          const x = (offset + i) * step
          const y = h - (data[i] / 4096) * h
          if (i === 0) ctx.moveTo(x, y)
          else ctx.lineTo(x, y)
        }
        ctx.stroke()
      })
    })
  }, [histories, armNames])

  return (
    <div className="bg-white border border-bd/30 rounded-lg p-3 shadow-card">
      <canvas
        ref={canvasRef}
        style={{ width: '100%', height: '200px' }}
        className="rounded bg-white border border-bd/40"
      />
      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2">
        {armNames.map((alias, armIdx) => (
          <div key={alias} className="flex items-center gap-1.5">
            <span
              className="inline-block w-3 h-1 rounded-full"
              style={{ backgroundColor: getArmPalette(armIdx)[0] }}
            />
            <span className="text-2xs text-tx2 font-medium">{alias}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function tempColor(temp: number): string {
  if (temp >= 65) return 'text-rd'
  if (temp >= 50) return 'text-yl'
  return 'text-gn'
}

function TemperatureBadges({ temperatures, armNames }: {
  temperatures: Record<string, Record<string, number>>
  armNames: string[]
}) {
  const { t } = useI18n()
  const hasAny = armNames.some((alias) => temperatures[alias] && Object.keys(temperatures[alias]).length > 0)
  if (!hasAny) return null

  return (
    <div className="space-y-2">
      <h4 className="text-xs text-tx2 uppercase tracking-wider font-medium">{t('servoTemperature')}</h4>
      {armNames.map((alias) => {
        const temps = temperatures[alias]
        if (!temps) return null
        return (
          <div key={alias} className="flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-xs">
            <span className="text-tx2 font-medium">{alias}:</span>
            {MOTOR_NAMES.map((motor) => {
              const val = temps[motor]
              if (val == null) return null
              return (
                <span key={motor} className={tempColor(val)}>
                  {motor} {val}&deg;C
                </span>
              )
            })}
          </div>
        )
      })}
    </div>
  )
}

export function ServoPanel({ state }: { state: SessionState }) {
  const { t } = useI18n()
  const [histories, setHistories] = useState<Record<string, ServoHistory>>({})
  const [temperatures, setTemperatures] = useState<Record<string, Record<string, number>>>({})
  const busy = state === 'teleoperating' || state === 'recording' || state === 'preparing'

  const poll = useCallback(async () => {
    if (busy) return
    const r = await fetch('/api/hardware/servos')
    const data = await r.json()
    if (data.error || !data.arms) return
    setHistories((prev) => {
      const next = { ...prev }
      for (const [alias, armData] of Object.entries(data.arms)) {
        const positions = (armData as any).positions
        if (typeof positions !== 'object') continue
        const armHistory = { ...(next[alias] || {}) }
        for (const motor of MOTOR_NAMES) {
          const val = positions[motor]
          if (val == null) continue
          const arr = armHistory[motor] || []
          armHistory[motor] = [...arr.slice(-(MAX_POINTS - 1)), val]
        }
        next[alias] = armHistory
      }
      return next
    })
    const nextTemps: Record<string, Record<string, number>> = {}
    for (const [alias, armData] of Object.entries(data.arms)) {
      const temps = (armData as any).temperatures
      if (typeof temps === 'object' && temps) {
        nextTemps[alias] = temps
      }
    }
    setTemperatures(nextTemps)
  }, [busy])

  useEffect(() => {
    if (busy) return
    poll()
    const timer = setInterval(poll, 500)
    return () => clearInterval(timer)
  }, [busy, poll])

  const armNames = Object.keys(histories)
  if (!armNames.length && !busy) {
    return (
      <div className="p-4">
        <div className="text-sm text-tx2">{t('servoLoading')}</div>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <h3 className="text-xs text-tx2 uppercase tracking-wider font-medium">{t('servoPositions')}</h3>
      {busy && (
        <div className="text-sm text-yl flex items-center gap-2 mb-2">
          <span className="w-2 h-2 rounded-full bg-yl animate-pulse" />
          {t('servoBusy')}
        </div>
      )}
      <UnifiedServoChart histories={histories} armNames={armNames} />
      <TemperatureBadges temperatures={temperatures} armNames={armNames} />
    </div>
  )
}
