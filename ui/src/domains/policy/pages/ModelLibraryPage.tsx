import { useEffect, useMemo, useState } from 'react'
import { useI18n } from '@/i18n'
import { useModelLibraryStore } from '@/domains/policy/store/useModelLibraryStore'

const MODEL_DISPLAY_PRIORITY: ReadonlyArray<string> = [
  'smolvla',
  'octo-small-1.5',
  'octo-base',
  'pi0',
  'openvla-7b',
  'smolvla-libero',
  'smolvla-vlabench',
  'openvla-libero-ft',
  'v-jepa-2-vit-l',
  'fluxvla-engine',
]

function compareModels(a: { slug: string; size_label: string }, b: { slug: string; size_label: string }): number {
  const ai = MODEL_DISPLAY_PRIORITY.indexOf(a.slug)
  const bi = MODEL_DISPLAY_PRIORITY.indexOf(b.slug)
  if (ai !== -1 || bi !== -1) {
    if (ai === -1) return 1
    if (bi === -1) return -1
    return ai - bi
  }
  return a.slug.localeCompare(b.slug)
}

export default function ModelLibraryPage() {
  const { t } = useI18n()
  const deployables = useModelLibraryStore((s) => s.deployables)
  const curated = useModelLibraryStore((s) => s.curated)
  const loadingDeployables = useModelLibraryStore((s) => s.loadingDeployables)
  const loadingCurated = useModelLibraryStore((s) => s.loadingCurated)
  const loadDeployables = useModelLibraryStore((s) => s.loadDeployables)
  const loadCurated = useModelLibraryStore((s) => s.loadCurated)

  const [filter, setFilter] = useState('')
  const [showFoundationSources, setShowFoundationSources] = useState(false)
  const [showFinetunes, setShowFinetunes] = useState(false)

  useEffect(() => {
    void loadDeployables()
    void loadCurated()
  }, [loadDeployables, loadCurated])

  const filtered = useMemo(() => {
    const needle = filter.trim().toLowerCase()
    if (!needle) return curated
    return curated.filter(
      (m) =>
        m.slug.toLowerCase().includes(needle)
        || m.repo_id.toLowerCase().includes(needle)
        || m.notes.toLowerCase().includes(needle),
    )
  }, [curated, filter])

  const sortedModels = useMemo(
    () => [...filtered].sort(compareModels),
    [filtered],
  )

  const generalModels = useMemo(
    () => sortedModels.filter((model) => model.track !== 'dataset_finetune'),
    [sortedModels],
  )

  const finetuneModels = useMemo(
    () => sortedModels.filter((model) => model.track === 'dataset_finetune'),
    [sortedModels],
  )

  const tildify = (path: string): string => {
    const home1 = '/Users/'
    const home2 = '/home/'
    if (path.startsWith(home1) || path.startsWith(home2)) {
      const parts = path.split('/')
      // /Users/<name>/...  →  ~/...
      return '~/' + parts.slice(3).join('/')
    }
    return path
  }

  const shouldShowFinetunes = showFinetunes || filter.trim().length > 0

  return (
    <div className="page-enter flex flex-col h-full overflow-y-auto">
      <div className="border-b border-bd/50 px-6 py-4 bg-sf flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight">{t('modelLibrary')}</h2>
        </div>
        <div className="flex items-center gap-3">
          <input
            type="text"
            placeholder={t('searchModels')}
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="bg-bg border border-bd text-tx px-3 py-2 rounded-lg text-sm font-mono w-[240px]
              focus:outline-none focus:border-ac"
          />
          <button
            type="button"
            onClick={() => {
              void loadDeployables()
              void loadCurated()
            }}
            disabled={loadingCurated || loadingDeployables}
            className="bg-bg border border-bd text-tx2 hover:text-tx px-3 py-2 rounded-lg text-sm
              disabled:opacity-50"
          >
            {loadingCurated || loadingDeployables ? t('refreshing') : t('refresh')}
          </button>
        </div>
      </div>

      <div className="flex-1 p-6 space-y-6">
        <div className="rounded-xl border border-bd/60 bg-sf px-4 py-3 text-sm text-tx">
          <div className="font-medium">{t('modelLibraryIntroTitle')}</div>
          <div className="mt-1 text-tx3 text-xs">{t('modelLibraryIntroBody')}</div>
        </div>

        <section className="bg-sf rounded-xl p-5 shadow-card shadow-inset-yl">
          <div className="mb-4">
            <h3 className="text-sm font-bold text-tx">{t('deployableModelsTitle')}</h3>
            <div className="mt-1 text-xs text-tx3">{t('deployableModelsBody')}</div>
          </div>
          {deployables.length === 0 ? (
            <div className="rounded-lg border border-bd/50 bg-bg px-4 py-3 text-xs text-tx3">
              {loadingDeployables ? t('loadingDeployableModels') : t('noDeployableModels')}
            </div>
          ) : (
            <div className="space-y-2">
              {deployables.map((entry) => (
                <div
                  key={entry.checkpoint}
                  className="flex items-start gap-4 px-3 py-3 rounded-lg border border-bd/50 hover:border-bd transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <code className="font-mono text-sm text-tx font-medium">{entry.name}</code>
                      <span className="text-2xs px-1.5 py-0.5 bg-gn/10 text-gn rounded font-mono">
                        {t('deployableNow')}
                      </span>
                      {entry.dataset && (
                        <span className="text-2xs px-1.5 py-0.5 bg-bd/30 text-tx2 rounded font-mono">
                          {entry.dataset}
                        </span>
                      )}
                      {typeof entry.steps === 'number' && entry.steps > 0 && (
                        <span className="text-2xs px-1.5 py-0.5 bg-bd/30 text-tx2 rounded font-mono">
                          {entry.steps.toLocaleString()} {t('steps')}
                        </span>
                      )}
                    </div>
                    <div className="text-2xs text-tx3 font-mono mt-1 break-all">
                      {tildify(entry.checkpoint)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="bg-sf rounded-xl p-5 shadow-card shadow-inset-yl">
          <div className="flex items-start justify-between gap-3 mb-4">
            <div>
              <h3 className="text-sm font-bold text-tx">{t('foundationSourcesTitle')}</h3>
              <div className="mt-1 text-xs text-tx3">{t('foundationSourcesBody')}</div>
            </div>
            <button
              type="button"
              onClick={() => setShowFoundationSources((v) => !v)}
              className="shrink-0 rounded-lg border border-bd px-3 py-1.5 text-xs text-tx2 hover:text-tx hover:border-ac"
            >
              {showFoundationSources ? t('hideFoundationSources') : t('showFoundationSources')}
            </button>
          </div>

          {!showFoundationSources ? (
            <div className="rounded-lg border border-bd/50 bg-bg px-4 py-3 text-xs text-tx3">
              {t('foundationSourcesCollapsedHint')}
            </div>
          ) : (
            <div className="space-y-6">
              <div className="rounded-lg border border-bd/50 bg-bg px-4 py-3 text-xs text-tx3">
                {t('foundationSourcesReadOnlyHint')}
              </div>

              {curated.length === 0 && !loadingCurated ? (
                <div className="text-center text-tx3 py-12 text-sm">{t('noCuratedModels')}</div>
              ) : (
                <>
                  {generalModels.length > 0 && (
                    <section className="bg-sf rounded-xl p-5 shadow-card shadow-inset-yl">
                      <div className="mb-4">
                        <h3 className="text-sm font-bold text-tx">{t('recommendedBaseModelsTitle')}</h3>
                        <div className="mt-1 text-xs text-tx3">{t('recommendedBaseModelsBody')}</div>
                      </div>
                      <div className="space-y-2">
                        {generalModels.map((model) => renderModelRow(model))}
                      </div>
                    </section>
                  )}

                  {finetuneModels.length > 0 && (
                    <section className="bg-sf rounded-xl p-5 shadow-card shadow-inset-yl">
                      <div className="flex items-start justify-between gap-3 mb-4">
                        <div>
                          <h3 className="text-sm font-bold text-tx">
                            {t('datasetFinetunesTitle')}
                            <span className="ml-2 text-2xs text-tx3 font-mono normal-case">({finetuneModels.length})</span>
                          </h3>
                          <div className="mt-1 text-xs text-tx3">{t('datasetFinetunesBody')}</div>
                        </div>
                        <button
                          type="button"
                          onClick={() => setShowFinetunes((v) => !v)}
                          className="shrink-0 rounded-lg border border-bd px-3 py-1.5 text-xs text-tx2 hover:text-tx hover:border-ac"
                        >
                          {shouldShowFinetunes ? t('hideDatasetFinetunes') : t('showDatasetFinetunes')}
                        </button>
                      </div>
                      {shouldShowFinetunes ? (
                        <div className="space-y-2">
                          {finetuneModels.map((model) => renderModelRow(model))}
                        </div>
                      ) : (
                        <div className="rounded-lg border border-bd/50 bg-bg px-4 py-3 text-xs text-tx3">
                          {t('datasetFinetunesCollapsedHint')}
                        </div>
                      )}
                    </section>
                  )}
                </>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  )

  function renderModelRow(model: typeof curated[number]) {
    return (
      <div
        key={model.slug}
        className="flex items-start gap-4 px-3 py-3 rounded-lg border border-bd/50 hover:border-bd transition-colors"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <code className="font-mono text-sm text-tx font-medium">{model.slug}</code>
            <span className="text-2xs px-1.5 py-0.5 bg-bd/30 text-tx2 rounded font-mono">
              {model.framework}
            </span>
            <span className="text-2xs px-1.5 py-0.5 bg-bd/30 text-tx2 rounded font-mono">
              {model.track === 'dataset_finetune' ? t('modelTagDatasetFinetune') : t('modelTagGeneralBase')}
            </span>
            <span className="text-2xs px-1.5 py-0.5 bg-bd/30 text-tx2 rounded font-mono">
              {model.access === 'public' ? t('modelTagPublic') : t('modelTagRequiresAuth')}
            </span>
            {model.size_label && (
              <span className="text-2xs px-1.5 py-0.5 bg-bd/30 text-tx2 rounded font-mono">
                {model.size_label}
              </span>
            )}
          </div>
          <div className="text-2xs text-tx3 font-mono mt-1 truncate">
            {model.source} · {model.repo_id}
          </div>
          {model.notes && (
            <div className="text-xs text-tx2 mt-1.5">{model.notes}</div>
          )}
        </div>
      </div>
    )
  }
}
