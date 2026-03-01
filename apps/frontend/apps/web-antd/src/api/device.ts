import { requestClient } from './request'

export interface BootstrapParams {
  ip: string
  username: string
  password: string
  deviceType?: string
  port?: number
}

export async function onlineDeviceApi(data: BootstrapParams) {
  return requestClient.post('/devices/online', data)
}

export async function offlineDeviceApi(data: BootstrapParams) {
  return requestClient.post('/devices/offline', data)
}

export async function restartDeviceApi(data: BootstrapParams) {
  return requestClient.post('/devices/restart', data)
}

export async function removeDeviceApi(ip: string) {
  return requestClient.post('/devices/remove', { ip })
}
