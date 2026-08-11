export const MODULE_STATE_CONTENT = Object.freeze({
  loading: { ariaBusy: true, message: "", canRetry: false },
  success: { ariaBusy: false, message: "", canRetry: false },
  empty: { ariaBusy: false, message: "内容正在整理中。", canRetry: false },
  error: { ariaBusy: false, message: "内容暂时无法加载，请稍后再试。", canRetry: true },
});

/** @param {'loading' | 'success' | 'empty' | 'error'} state */
export function getModuleStateContent(state) {
  return MODULE_STATE_CONTENT[state];
}
