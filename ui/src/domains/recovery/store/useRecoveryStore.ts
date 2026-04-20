import { create } from 'zustand'
import { useHardwareStore } from '@/domains/hardware/store/useHardwareStore'

const RECOVERY = '/api/recovery'
const RUNTIME_INFO = '/api/system/runtime-info'

export interface RecoveryFault {
  fault_type: string
  device_alias: string
  message: string
  timestamp: number
}

export interface RecoveryGuide {
  can_recheck: boolean
  step_count: number
}

interface RecoveryStore {
  faults: RecoveryFault[]
  guides: Record<string, RecoveryGuide> | null
  rechecking: boolean
  restarting: boolean
  fetchFaults: () => Promise<void>
  fetchGuides: () => Promise<void>
  recheckHardware: () => Promise<RecoveryFault[]>
  restartDashboard: () => Promise<void>
  handleDashboardEvent: (event: any) => void
}

async function waitForDashboardRecovery(timeoutMs: number = 30000): Promise<void> {
  const startedAt = Date.now()
  while (Date.now() - startedAt < timeoutMs) {
    await new Promise((resolve) => window.setTimeout(resolve, 1000))
    try {
      const response = await fetch(RUNTIME_INFO, { cache: 'no-store' })
      if (response.ok) {
        window.location.reload()
        return
      }
    } catch {
      // Dashboard is still restarting. Keep polling until timeout.
    }
  }
  throw new Error('Dashboard restart timed out')
}

export const useRecoveryStore = create<RecoveryStore>((set) => ({
  faults: [],
  guides: null,
  rechecking: false,
  restarting: false,

  fetchFaults: async () => {
    const response = await fetch(`${RECOVERY}/faults`)
    if (!response.ok) {
      throw new Error(`Failed to fetch recovery faults: ${response.status}`)
    }
    const data = await response.json()
    set({ faults: Array.isArray(data.faults) ? data.faults : [] })
  },

  fetchGuides: async () => {
    const response = await fetch(`${RECOVERY}/guides`)
    if (!response.ok) {
      throw new Error(`Failed to fetch recovery guides: ${response.status}`)
    }
    set({ guides: await response.json() })
  },

  recheckHardware: async () => {
    set({ rechecking: true })
    try {
      const response = await fetch(`${RECOVERY}/recheck`, { method: 'POST' })
      if (!response.ok) {
        throw new Error(`Failed to recheck hardware: ${response.status}`)
      }
      const data = await response.json()
      const faults = Array.isArray(data.faults) ? data.faults : []
      set({ faults })
      await useHardwareStore.getState().fetchHardwareStatus()
      return faults
    } finally {
      set({ rechecking: false })
    }
  },

  restartDashboard: async () => {
    set({ restarting: true })
    try {
      const response = await fetch(`${RECOVERY}/restart-dashboard`, { method: 'POST' })
      if (!response.ok) {
        throw new Error(`Failed to restart dashboard: ${response.status}`)
      }
      await waitForDashboardRecovery()
    } finally {
      set({ restarting: false })
    }
  },

  handleDashboardEvent: (event) => {
    if (event.type === 'dashboard.fault.detected') {
      const fault: RecoveryFault = {
        fault_type: event.fault_type,
        device_alias: event.device_alias,
        message: event.message,
        timestamp: event.timestamp,
      }
      set((state) => ({
        faults: [
          ...state.faults.filter(
            (item) => !(item.fault_type === fault.fault_type && item.device_alias === fault.device_alias),
          ),
          fault,
        ],
      }))
      return
    }

    if (event.type === 'dashboard.fault.resolved') {
      set((state) => ({
        faults: state.faults.filter(
          (item) => !(item.fault_type === event.fault_type && item.device_alias === event.device_alias),
        ),
      }))
    }
  },
}))
