/** Same key as Players page — pre-match team strength uses this preference. */
export const IMPACT_FORMULA_STORAGE_KEY = "playersImpactFormula";

/** @returns {"br_bor_v1" | "classic_bpr_csa"} */
export function readImpactFormulaPreference() {
  try {
    const s = window.localStorage.getItem(IMPACT_FORMULA_STORAGE_KEY);
    return s === "classic_bpr_csa" ? "classic_bpr_csa" : "br_bor_v1";
  } catch {
    return "br_bor_v1";
  }
}
