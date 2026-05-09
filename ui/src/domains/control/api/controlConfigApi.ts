import { api, postJson } from '@/shared/api/client'

export interface ControlRecordConfig {
  task: string
  num_episodes: number
  episode_time_s: number
  reset_time_s: number
  dataset_name: string
  fps: number
  use_cameras: boolean
}

export interface ControlTrainConfig {
  dataset_name: string
  policy_type: string
  steps: number
  device: string
}

export interface ControlInferConfig {
  checkpoint_path: string
  source_dataset: string
  dataset_name: string
  task: string
  num_episodes: number
  episode_time_s: number
  use_cameras: boolean
}

export function fetchControlRecordConfig() {
  return api('/api/system/control-record-config') as Promise<ControlRecordConfig>
}

export function saveControlRecordConfig(payload: ControlRecordConfig) {
  return postJson('/api/system/control-record-config', payload)
}

export function fetchControlTrainConfig() {
  return api('/api/system/control-train-config') as Promise<ControlTrainConfig>
}

export function saveControlTrainConfig(payload: ControlTrainConfig) {
  return postJson('/api/system/control-train-config', payload)
}

export function fetchControlInferConfig() {
  return api('/api/system/control-infer-config') as Promise<ControlInferConfig>
}

export function saveControlInferConfig(payload: ControlInferConfig) {
  return postJson('/api/system/control-infer-config', payload)
}
