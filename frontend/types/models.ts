// Общие типы доменных сущностей backend (frontend) и подписи перечислений.
// Соответствуют схемам ответов API (app/src/app/api/schemas).

// ---------- Пользователи ----------

export type UserRole = 'admin' | 'manager'

export const ROLE_LABELS: Record<UserRole, string> = {
  admin: 'Администратор',
  manager: 'Менеджер',
}

export interface User {
  id: number
  username: string
  role: UserRole
  telegram_id: number | null
  is_active: boolean
  created_at: string
  updated_at: string
}

/** Менеджер в модалке назначения (id + username достаточно, role/is_active — фильтр) */
export interface ManagerUser {
  id: number
  username: string
  role: UserRole
  is_active: boolean
}

// ---------- Категории и объекты ----------

export interface Category {
  id: number
  name: string
  button_text: string | null
  sort_order: number
  is_active: boolean
}

export interface Obj {
  id: number
  category_id: number
  name: string
  short_description: string
  sort_order: number
  is_active: boolean
  has_pdf: boolean
}

// ---------- Поля заявки ----------

export type FieldType = 'text' | 'number' | 'date' | 'time' | 'select'

export const FIELD_TYPE_LABELS: Record<FieldType, string> = {
  text: 'Текст',
  number: 'Число',
  date: 'Дата',
  time: 'Время (часы и минуты)',
  select: 'Выбор из вариантов',
}

/** Справочник поля (request_available_fields) */
export interface FieldDef {
  id: number
  code: string
  type: FieldType
  label: string
  is_required_default: boolean
  meta_data: Record<string, unknown> | null
}

/** Значение поля в заявке (request_fields + справочник) */
export interface RequestFieldValue {
  field_id: number
  field_code: string
  field_label: string
  value: string | null
}

// ---------- Заявки ----------

export type RequestStatus =
  | 'new'
  | 'approved'
  | 'rejected'
  | 'completed'
  | 'cancelled_by_customer'

/** Порядок статусов в фильтрах и валидации deep-link'ов */
export const REQUEST_STATUSES: readonly RequestStatus[] = [
  'new',
  'approved',
  'rejected',
  'completed',
  'cancelled_by_customer',
]

/** Подписи статусов для фильтров (бейдж заявки — StatusBadge) */
export const REQUEST_STATUS_LABELS: Record<RequestStatus, string> = {
  new: 'Новые',
  approved: 'Подтверждённые',
  rejected: 'Отклонённые',
  completed: 'Выполненные',
  cancelled_by_customer: 'Отменённые',
}

export interface Request {
  id: number
  visitor_id: number
  object_id: number
  phone: string
  fields: RequestFieldValue[]
  status: RequestStatus
  confirmed_at: string | null
  created_at: string
  updated_at: string
}

// ---------- Посетители ----------

export interface Visitor {
  id: number
  telegram_id: number
  full_name: string
  phone: string | null
  consent_given: boolean
  is_blocked: boolean
  created_at: string
}

// ---------- Устройства и сессии ----------

export interface Device {
  id: number
  user_id: number
  device_id: string
  user_agent: string | null
  created_at: string
  last_seen_at: string
}

export interface Session {
  id: number
  device_id: number
  user_id: number
  refresh_token_jti: string
  is_active: boolean
  created_at: string
  revoked_at: string | null
}
