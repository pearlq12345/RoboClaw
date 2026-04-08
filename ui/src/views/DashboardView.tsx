import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDashboard, type SessionState } from '../controllers/dashboard'
import { useI18n } from '../controllers/i18n'

type BtnVariant = 'gn' | 'rd' | 'yl' | 'ac'
const variantCls: Record<BtnVariant, string> = {
  gn: 'border-gn/60 text-gn hover:border-gn hover:bg-gn/10',
  rd: 'border-rd/60 text-rd hover:border-rd hover:bg-rd/10',
  yl: 'border-yl/60 text-yl hover:border-yl hover:bg-yl/10',
  ac: 'border-ac/60 text-ac hover:border-ac hover:bg-ac/10',
}

function Btn({
  children,
  disabled,
  onClick,
  variant = 'ac',
}: {
  children: React.ReactNode
  disabled?: boolean
  onClick?: () => void
  variant?: BtnVariant
}) {
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      className={`px-3.5 py-1.5 border rounded text-sm bg-white transition-colors active:scale-[0.97]
        disabled:opacity-30 disabled:cursor-not-allowed ${variantCls[variant]}`}
    >
      {children}
    </button>
  )
}

function canDo(state: SessionState, hwReady: boolean) {
  const idle = state === 'idle'
  const tele = state === 'teleoperating'
  const rec = state === 'recording'
  return {
    teleopStart: idle && hwReady,
    teleopStop: tele,
    recStart: (idle || tele) && hwReady,
    recStop: rec,
    saveEp: rec,
    discardEp: rec,
  }
}

export default function DashboardView() {
  const store = useDashboard()
  const { session, logs, datasets, loading, hardwareStatus: hwStatus } = store
  const { state, episode_phase: episodePhase, saved_episodes: savedEpisodes, target_episodes: targetEpisodes } = session
  const hwReady = hwStatus?.ready ?? false
  const ok = canDo(state, hwReady)
  const logRef = useRef<HTMLDivElement>(null)
  const { t } = useI18n()
  const navigate = useNavigate()

  const stateLabel: Record<SessionState, string> = {
    idle: t('stateConnected'),
    preparing: t('hwInitializing'),
    teleoperating: t('stateTeleoperating'),
    recording: t('stateRecording'),
  }
  const stateBadgeCls: Record<SessionState, string> = {
    idle: 'bg-gn/10 text-gn',
    preparing: 'bg-yl/10 text-yl',
    teleoperating: 'bg-ac/10 text-ac',
    recording: 'bg-yl/10 text-yl',
  }

  const [task, setTask] = useState('')
  const [numEp, setNumEp] = useState(10)
  const [episodeTime, setEpisodeTime] = useState(300)
  const [resetTime, setResetTime] = useState(10)

  useEffect(() => {
    store.loadDatasets()
    store.addLog('RoboClaw UI loaded')
    store.fetchHardwareStatus()
    const hwInterval = setInterval(() => {
      if (document.visibilityState === 'visible') store.fetchHardwareStatus()
    }, 5000)
    return () => clearInterval(hwInterval)
  }, [])

  useEffect(() => {
    logRef.current?.scrollTo(0, logRef.current.scrollHeight)
  }, [logs])

  function handleRecordStart() {
    if (!task.trim()) { store.addLog(t('fillTaskDesc'), 'err'); return }
    store.doRecordStart({
      task: task.trim(),
      num_episodes: numEp,
      episode_time_s: episodeTime,
      reset_time_s: resetTime,
    })
  }

  return (
    <div className="flex flex-col h-full">
      {state !== 'idle' && (
        <div className="flex items-center gap-3 px-4 py-2 border-b border-bd/40 text-sm flex-wrap">
          <span className={`px-2 py-0.5 rounded text-xs font-semibold ${stateBadgeCls[state]}`}>
            {stateLabel[state]}
          </span>
          {state === 'recording' && (
            <span className="text-tx2">{t('savedEpisodes')}: {savedEpisodes} / {targetEpisodes}</span>
          )}
        </div>
      )}

      {session.error && (
        <div className="px-4 py-2 bg-rd/10 border-b border-rd/30 border-l-4 border-l-rd text-rd text-sm font-mono whitespace-pre-wrap">
          {session.error}
        </div>
      )}

      {!hwReady && hwStatus && (
        <div className="px-4 py-2 bg-yl/10 border-b border-yl/30 border-l-4 border-l-yl text-yl text-sm">
          {hwStatus.missing.join(' · ')}
        </div>
      )}

      {session.rerun_web_port > 0 && (state === 'teleoperating' || state === 'recording') && (
        <div className="border-b border-bd bg-black/5">
          <iframe
            src={`${location.protocol}//${location.hostname}:${session.rerun_web_port}`}
            className="w-full border-0"
            style={{ height: '400px' }}
            title="Rerun Visualization"
          />
        </div>
      )}

      <div className="flex-1 grid grid-cols-[1fr_320px] overflow-hidden max-[900px]:grid-cols-1">
        <div className="flex flex-col overflow-y-auto p-4 space-y-3">
          {/* Hardware status card */}
          <div
            onClick={() => navigate('/settings')}
            className="bg-white border border-bd/30 rounded-lg p-4 shadow-card cursor-pointer
                       hover:border-ac/40 hover:shadow-glow-ac transition-all group"
          >
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <span className="text-2xs text-tx2 font-medium">{t('arms')}</span>
                <div className="flex items-center gap-1">
                  {hwStatus?.arms.map(arm => (
                    <span key={arm.alias}
                      className={`w-2.5 h-2.5 rounded-full ${!arm.connected ? 'bg-rd' : !arm.calibrated ? 'bg-yl' : 'bg-gn'}`}
                      title={arm.alias + (!arm.connected ? ' — disconnected' : !arm.calibrated ? ' — uncalibrated' : '')}
                    />
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-2xs text-tx2 font-medium">{t('cameras')}</span>
                <div className="flex items-center gap-1">
                  {hwStatus?.cameras.map(cam => (
                    <span key={cam.alias}
                      className={`w-2.5 h-2.5 rounded-full ${cam.connected ? 'bg-gn' : 'bg-rd'}`}
                      title={cam.alias}
                    />
                  ))}
                </div>
              </div>
            </div>
            <div className="text-2xs mt-1.5 text-tx3 group-hover:text-ac transition-colors">
              {hwStatus?.ready ? t('hwReady') : `${hwStatus?.missing?.length ?? 0} ${t('warnings')}`}
            </div>
          </div>

          {/* Teleop card */}
          <div className="bg-white border border-bd/30 rounded-lg p-5 shadow-card">
            <h3 className="text-xs text-tx2 uppercase tracking-wider mb-2 font-medium">{t('teleoperation')}</h3>
            <div className="flex gap-2 flex-wrap">
              <Btn variant="ac" disabled={!ok.teleopStart || !!loading} onClick={store.doTeleopStart}>
                {loading === 'teleop' ? t('startingTeleop') : t('startTeleop')}
              </Btn>
              <Btn variant="yl" disabled={!ok.teleopStop || !!loading} onClick={store.doTeleopStop}>
                {t('stopTeleop')}
              </Btn>
            </div>
            {(loading === 'teleop' || state === 'teleoperating') && (
              <div className="mt-2 flex items-center gap-2 text-sm text-ac">
                <span className="inline-block w-2 h-2 rounded-full bg-ac animate-pulse" />
                {loading === 'teleop' ? t('hwInitializing') : t('stateTeleoperating')}
              </div>
            )}
          </div>

          {/* Recording card */}
          <div className="bg-white border border-bd/30 rounded-lg p-5 shadow-card">
            <h3 className="text-xs text-tx2 uppercase tracking-wider mb-3 font-medium">{t('recording')}</h3>

            <div className="flex gap-2 flex-wrap mb-3">
              <label className="flex flex-col gap-1 text-xs text-tx2 flex-1 min-w-[160px]">
                {t('taskDesc')}
                <input
                  value={task}
                  onChange={(e) => setTask(e.target.value)}
                  placeholder="Pick up the red block"
                  className="bg-sf2 border border-bd text-tx px-3 py-2 rounded text-sm focus:outline-none focus:border-ac focus:shadow-glow-ac placeholder:text-tx3"
                />
              </label>
            </div>

            <div className="flex gap-2 flex-wrap mb-3 items-end">
              <label className="flex flex-col gap-1 text-xs text-tx2 w-[90px]">
                {t('numEpisodes')}
                <input
                  type="number"
                  value={numEp}
                  onChange={(e) => setNumEp(Number(e.target.value) || 10)}
                  min={1}
                  className="bg-sf2 border border-bd text-tx px-3 py-2 rounded text-sm focus:outline-none focus:border-ac focus:shadow-glow-ac placeholder:text-tx3"
                />
              </label>
              <label className="flex flex-col gap-1 text-xs text-tx2 w-[100px]">
                Ep time (s)
                <input
                  type="number"
                  value={episodeTime}
                  onChange={(e) => setEpisodeTime(Number(e.target.value) || 300)}
                  min={1}
                  className="bg-sf2 border border-bd text-tx px-3 py-2 rounded text-sm focus:outline-none focus:border-ac focus:shadow-glow-ac placeholder:text-tx3"
                />
              </label>
              <label className="flex flex-col gap-1 text-xs text-tx2 w-[100px]">
                Reset (s)
                <input
                  type="number"
                  value={resetTime}
                  onChange={(e) => setResetTime(Number(e.target.value) || 10)}
                  min={0}
                  className="bg-sf2 border border-bd text-tx px-3 py-2 rounded text-sm focus:outline-none focus:border-ac focus:shadow-glow-ac placeholder:text-tx3"
                />
              </label>
              <div className="flex gap-2 flex-1 justify-end">
                <Btn variant="gn" disabled={!ok.recStart || !!loading} onClick={handleRecordStart}>
                  {loading === 'record' ? t('startingRecord') : t('startRecording')}
                </Btn>
                <Btn variant="rd" disabled={!ok.recStop} onClick={store.doRecordStop}>
                  {t('stopRecording')}
                </Btn>
              </div>
            </div>

            {state === 'recording' && (
              <RecordingProgress
                episodePhase={episodePhase}
                savedEpisodes={savedEpisodes}
                targetEpisodes={targetEpisodes}
                onSave={store.doSaveEpisode}
                onDiscard={store.doDiscardEpisode}
                onSkipReset={store.doSkipReset}
                t={t}
              />
            )}
          </div>
        </div>

        {/* Right sidebar */}
        <div className="bg-sf/60 border-l border-bd/40 flex flex-col overflow-hidden max-[900px]:border-l-0 max-[900px]:border-t max-[900px]:max-h-[50vh]">
          <div className="px-3 py-2.5 border-b border-bd/40">
            <div className="flex items-center justify-between">
              <h3 className="text-xs text-tx2 uppercase tracking-wider font-medium">{t('datasets')}</h3>
              <button
                onClick={store.loadDatasets}
                className="px-2.5 py-0.5 border border-ac/60 text-ac rounded text-xs hover:border-ac hover:bg-ac/10"
              >
                {t('refresh')}
              </button>
            </div>
          </div>
          <div className="overflow-y-auto flex-1 p-2">
            {datasets.length === 0 && (
              <div className="text-tx2 text-center py-4 text-sm">{t('noDatasets')}</div>
            )}
            {datasets.map((d) => (
              <div
                key={d.name}
                className="bg-white border border-bd/30 rounded-lg shadow-card mb-1.5 px-3 py-2 flex items-center gap-2 text-sm"
              >
                <span className="flex-1 font-semibold text-tx">{d.name}</span>
                <span className="text-tx2 text-xs whitespace-nowrap">
                  {d.total_episodes != null ? `${d.total_episodes} ep` : ''}
                  {d.total_frames != null ? ` | ${d.total_frames} fr` : ''}
                </span>
                <button
                  onClick={() => {
                    if (confirm(`${t('deleteConfirm')} "${d.name}"?`)) store.deleteDataset(d.name)
                  }}
                  className="px-2 py-0.5 border border-rd/60 text-rd rounded text-xs hover:border-rd hover:bg-rd/10"
                >
                  {t('del')}
                </button>
              </div>
            ))}
          </div>

          <div className="px-3 py-2.5 border-t border-bd/40">
            <div className="flex items-center justify-between">
              <h3 className="text-xs text-tx2 uppercase tracking-wider font-medium">{t('log')}</h3>
              <button
                onClick={store.clearLog}
                className="px-2.5 py-0.5 border border-bd text-tx2 rounded-sm text-xs hover:bg-bd/30"
              >
                {t('clear')}
              </button>
            </div>
          </div>
          <div ref={logRef} className="flex-1 overflow-y-auto px-3 py-1 font-mono text-xs">
            {logs.map((entry, i) => (
              <div
                key={i}
                className={`py-0.5 border-b border-bd/40 ${
                  entry.cls === 'err' ? 'text-rd' : entry.cls === 'ok' ? 'text-gn' : 'text-tx2'
                }`}
              >
                <span className="text-tx3 mr-2 text-2xs">{entry.time}</span>
                {entry.message}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function RecordingProgress({
  episodePhase,
  savedEpisodes,
  targetEpisodes,
  onSave,
  onDiscard,
  onSkipReset,
  t,
}: {
  episodePhase: string
  savedEpisodes: number
  targetEpisodes: number
  onSave: () => void
  onDiscard: () => void
  onSkipReset: () => void
  t: (key: any) => string
}) {
  return (
    <>
      <div className="mb-3">
        <div className="flex justify-between text-sm text-tx mb-1">
          <span>{t('savedEpisodes')}: {savedEpisodes} / {targetEpisodes}</span>
          <span>{targetEpisodes > 0 ? Math.round((savedEpisodes / targetEpisodes) * 100) : 0}%</span>
        </div>
        <div className="w-full h-2.5 bg-bd rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-ac2 to-ac rounded-full transition-all duration-500"
            style={{ width: `${targetEpisodes > 0 ? (savedEpisodes / targetEpisodes) * 100 : 0}%` }}
          />
        </div>
      </div>

      <div className="flex gap-2 flex-wrap mb-3">
        <Btn variant="gn" disabled={episodePhase !== 'recording'} onClick={onSave}>
          {episodePhase === 'saving' ? t('episodeSaving') : t('saveEpisode')}
        </Btn>
        <Btn variant="yl" disabled={episodePhase !== 'recording'} onClick={onDiscard}>
          {t('discardEpisode')}
        </Btn>
        {episodePhase === 'resetting' && (
          <Btn variant="ac" onClick={onSkipReset}>
            {t('skipReset')}
          </Btn>
        )}
      </div>
      <div className="flex items-center gap-2 text-sm">
        {episodePhase === 'recording' && (
          <>
            <span className="w-2 h-2 rounded-full bg-ac animate-pulse" />
            <span className="text-ac">{t('stateRecording')}</span>
          </>
        )}
        {episodePhase === 'saving' && (
          <>
            <span className="w-2 h-2 rounded-full bg-yl animate-pulse" />
            <span className="text-yl">{t('episodeSaving')}</span>
          </>
        )}
        {episodePhase === 'resetting' && (
          <>
            <span className="w-2 h-2 rounded-full bg-yl animate-pulse" />
            <span className="text-yl">{t('episodeResetting')}</span>
          </>
        )}
        {!episodePhase && (
          <>
            <span className="w-2 h-2 rounded-full bg-ac animate-pulse" />
            <span className="text-ac">{t('stateRecording')}</span>
          </>
        )}
      </div>
    </>
  )
}
