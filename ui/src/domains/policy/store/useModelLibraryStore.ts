import { create } from 'zustand'
import { api, postJson } from '@/shared/api/client'

const MODELS = '/api/models'
const POLICIES = '/api/policies'

export interface CuratedModel {
  slug: string
  source: string
  repo_id: string
  revision: string
  framework: string
  notes: string
  access: string
  track: string
  size_label: string
  v1_ready: boolean
  cached: boolean
}

export interface CachedModelEntry {
  source: string
  repo_id: string
  revision: string
}

export interface PullResult {
  slug: string
  local_path: string
  files: string[]
  bytes_downloaded: number
  cached_hit: boolean
}

export interface DeployableModelEntry {
  name: string
  checkpoint: string
  dataset?: string
  steps?: number
}

interface ModelLibraryStore {
  deployables: DeployableModelEntry[]
  curated: CuratedModel[]
  cacheRoot: string
  hiddenCount: number
  totalCurated: number
  cachedEntries: CachedModelEntry[]
  localEntries: CachedModelEntry[]
  localRoot: string
  loadingDeployables: boolean
  loadingCurated: boolean
  loadingCached: boolean
  pullingSlug: string | null
  lastPullResult: PullResult | null
  lastError: string

  loadDeployables: () => Promise<void>
  loadCurated: () => Promise<void>
  loadCached: () => Promise<void>
  loadLocal: () => Promise<void>
  pullModel: (slug: string, force?: boolean) => Promise<void>
  clearError: () => void
}

export const useModelLibraryStore = create<ModelLibraryStore>((set, get) => ({
  deployables: [],
  curated: [],
  cacheRoot: '',
  hiddenCount: 0,
  totalCurated: 0,
  cachedEntries: [],
  localEntries: [],
  localRoot: '',
  loadingDeployables: false,
  loadingCurated: false,
  loadingCached: false,
  pullingSlug: null,
  lastPullResult: null,
  lastError: '',

  loadDeployables: async () => {
    set({ loadingDeployables: true, lastError: '' })
    try {
      const data = await api(POLICIES)
      set({ deployables: Array.isArray(data) ? data : [] })
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      set({ lastError: message })
    } finally {
      set({ loadingDeployables: false })
    }
  },

  loadCurated: async () => {
    set({ loadingCurated: true, lastError: '' })
    try {
      const data = await api(`${MODELS}/curated`)
      set({
        curated: data.items ?? [],
        cacheRoot: data.cache_root ?? '',
        hiddenCount: data.hidden_count ?? 0,
        totalCurated: data.total_curated ?? (data.items?.length ?? 0),
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      set({ lastError: message })
    } finally {
      set({ loadingCurated: false })
    }
  },

  loadCached: async () => {
    set({ loadingCached: true })
    try {
      const data = await api(`${MODELS}/cached`)
      set({ cachedEntries: data.items ?? [] })
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      console.warn('Failed to load cached models:', message)
    } finally {
      set({ loadingCached: false })
    }
  },

  loadLocal: async () => {
    try {
      const data = await api(`${MODELS}/local`)
      set({
        localEntries: data.items ?? [],
        localRoot: data.root ?? '',
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      console.warn('Failed to load local models:', message)
    }
  },

  pullModel: async (slug: string, force = false) => {
    set({ pullingSlug: slug, lastError: '', lastPullResult: null })
    try {
      const result = await postJson(`${MODELS}/pull`, { slug, force })
      set({ lastPullResult: result })
      // refresh both lists so cached badges update
      await Promise.all([get().loadCurated(), get().loadCached()])
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      set({ lastError: message })
    } finally {
      set({ pullingSlug: null })
    }
  },

  clearError: () => set({ lastError: '' }),
}))
