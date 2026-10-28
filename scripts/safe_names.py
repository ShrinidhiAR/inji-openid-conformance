"""Fixed membership for values that may leave the harness. Anything else is mapped, never copied."""
import pathlib
CATEGORIES=frozenset({'actual_result_evidence_requires_visual_review','bridge_component','bridge_http_status','bridge_module_identifier','bridge_response_size','bridge_transport','bridge_unsupported_module','credential_result_shape','empty_credential_results','handoff_component','issuer_browser_shape','issuer_browser_url','issuer_handoff_configuration','issuer_handoff_suite','issuer_handoff_unsupported_module','official_library_integrity','readiness_content_type','request_details','request_identifier','request_nonce','request_profile','request_transaction','response_code_contract','result_screenshot_browser_missing','result_screenshot_render_failure','result_transaction','status_check_shape','suite_api_failure','suite_module_identifier','suite_origin','synthetic_handoff_failure','timeout_positive','verification_result_missing','wallet_handoff_incomplete','wallet_input_request','wallet_submit_scope'
})
_PINNED=pathlib.Path(__file__).with_name('condition_classes.txt')
CONDITION_CLASSES=frozenset(l.strip() for l in _PINNED.read_text().splitlines() if l.strip() and not l.startswith('#'))
def category(error):
 text=str(error)
 return text if type(error).__name__ in {'HarnessError','ContractError'} and text in CATEGORIES else 'handoff_incomplete_or_failed'
def conditions(entries,limit=60):
 """Return None when the log is not a list (diagnostic absent). Empty list means no findings."""
 if not isinstance(entries,list):return None
 out=[]
 for e in entries:
  if not isinstance(e,dict):continue
  result=e.get('result')
  if result not in {'FAILURE','WARNING','REVIEW'}:continue
  source=e.get('src') or e.get('source')
  out.append({'source':source if isinstance(source,str) and source in CONDITION_CLASSES else 'other_unlisted_condition','result':result})
  if len(out)>=limit:break
 return out
