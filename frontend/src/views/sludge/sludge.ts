/** 污泥脱水台账：列表页与详情页共用的接口、常量与动作判断。
 *
 * 判断逻辑集中在这一份里：无论从列表行还是详情页打开加药弹窗，
 * 能不能登记、提示什么都完全一致。
 */
import { request } from '@/api/client'

export interface SludgeRow {
  id: number
  机组编号: string
  所属厂站: string
  机组类型: string
  进泥量: number | null
  出泥含水率: number | null
  絮凝剂用量: number | null
  运行功率: number | null
  机组状态: SludgeStatus
  status: SludgeStatus
  开始时间: string | null
  结束时间: string | null
  pending: boolean
  readonly: boolean
  abnormal: boolean
}

export type SludgeStatus = '待进料' | '运行中' | '冲洗中' | '已停机'

export const STATUS_STOPPED: SludgeStatus = '已停机'
export const ACTIVE_STATUSES: SludgeStatus[] = ['待进料', '运行中', '冲洗中']
export const STATUS_OPTIONS: SludgeStatus[] = ['待进料', '运行中', '冲洗中', '已停机']

export const ACTION_FEED = '启动进料'
export const ACTION_FLUSH = '开始冲洗'
export const ACTION_DOSE = '加药登记'

export const ENDPOINT = '/api/sludge'

export interface ActionResponse {
  ok: boolean
  message: string
  entry: SludgeRow | null
}

export interface ListResponse {
  items: SludgeRow[]
  total: number
  page: number
  size: number
}

export interface CreateForm {
  机组编号: string
  所属厂站: string
  机组类型: string
  运行功率: string
  进泥量: string
}

export interface DoseForm {
  絮凝剂用量: string
  出泥含水率: string
}

export interface ListParams {
  keyword?: string
  status?: string
}

/** 行内允许展示的动作，随状态变化；已停机历史记录一个动作都不给。 */
export function availableActions(row: Pick<SludgeRow, '机组状态'>): string[] {
  switch (row.机组状态) {
    case '待进料':
      return [ACTION_FEED]
    case '运行中':
      return [ACTION_FLUSH, ACTION_DOSE]
    case '冲洗中':
      return [ACTION_DOSE]
    case STATUS_STOPPED:
      return []
    default:
      return []
  }
}

/** 某条记录此刻能否打开加药弹窗；被拦下时给出与详情页一致的说明。 */
export function doseEligibility(row: Pick<SludgeRow, '机组状态'>): { allowed: boolean; reason: string } {
  if (row.机组状态 === STATUS_STOPPED) {
    return { allowed: false, reason: '该运行记录已停机归档，仅供查询，不能再补加药登记' }
  }
  if (!ACTIVE_STATUSES.includes(row.机组状态)) {
    return { allowed: false, reason: `当前状态「${row.机组状态}」不支持加药登记` }
  }
  return { allowed: true, reason: '' }
}

function asError(payload: unknown, fallback: string): Error {
  const message = (payload as { detail?: string } | null)?.detail
  return new Error(message || fallback)
}

export async function fetchList(params: ListParams = {}): Promise<ListResponse> {
  const query = new URLSearchParams()
  if (params.keyword) query.set('keyword', params.keyword.trim())
  if (params.status) query.set('status', params.status)
  const suffix = query.toString() ? `?${query.toString()}` : ''
  const response = await request(`${ENDPOINT}${suffix}`)
  if (!response.ok) throw asError(await response.json().catch(() => null), '脱水机组列表读取失败')
  return (await response.json()) as ListResponse
}

export async function fetchStats(): Promise<Record<string, number>> {
  const response = await request(`${ENDPOINT}/stats`)
  if (!response.ok) throw new Error('台账统计读取失败')
  return (await response.json()) as Record<string, number>
}

export async function fetchDetail(id: number): Promise<SludgeRow> {
  const response = await request(`${ENDPOINT}/${id}`)
  if (response.status === 404) throw asError(await response.json().catch(() => null), '记录不存在')
  if (!response.ok) throw asError(await response.json().catch(() => null), '脱水机组明细读取失败')
  return (await response.json()) as SludgeRow
}

export async function createEntry(values: Partial<CreateForm>): Promise<ActionResponse> {
  const response = await request(ENDPOINT, {
    method: 'POST',
    body: JSON.stringify({ values }),
  })
  return (await response.json()) as ActionResponse
}

/** 执行状态动作。action 放在 values 里，与后端 EntryPayload 对齐。 */
export async function submitAction(
  id: number,
  action: string,
  values: Record<string, string | number> = {},
): Promise<ActionResponse> {
  const response = await request(`${ENDPOINT}/${id}/actions`, {
    method: 'POST',
    body: JSON.stringify({ values: { action, ...values } }),
  })
  return (await response.json()) as ActionResponse
}

export function isBlank(value: string): boolean {
  return value.trim() === ''
}
