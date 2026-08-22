import { ref } from "vue";

/** 公开问卷流程的内联错误提示（App.vue 274/746/818 行使用）。 */
export const error = ref("");

/** 后台提示改为右上角浮动弹框：成功 3s 自动消失、普通错误 6s、
 *  严重错误常驻（可关闭，可跳转「查看客户」）。切换页签/详情时 clearToasts。 */
export type ToastKind = "success" | "error" | "severe";

export interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
  leadId: number | null;
  leadName: string | null;
}

const AUTO_DISMISS_MS: Record<Exclude<ToastKind, "severe">, number> = {
  success: 3000,
  error: 6000,
};

export const toasts = ref<Toast[]>([]);

let toastSequence = 0;

export function pushToast(
  kind: ToastKind,
  message: string,
  opts: { leadId?: number | null; leadName?: string | null } = {}
): number {
  const id = ++toastSequence;
  const toast: Toast = {
    id,
    kind,
    message,
    leadId: opts.leadId ?? null,
    leadName: opts.leadName ?? null,
  };
  toasts.value = [...toasts.value, toast];
  if (kind !== "severe") {
    window.setTimeout(() => dismissToast(id), AUTO_DISMISS_MS[kind]);
  }
  return id;
}

export function dismissToast(id: number): void {
  toasts.value = toasts.value.filter((toast) => toast.id !== id);
}

export function clearToasts(): void {
  toasts.value = [];
}
