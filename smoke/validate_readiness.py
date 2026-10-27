"""Strict validators for isolated alpha smoke. No credential issuance."""
BASE='http://localhost:8099'
CONFIG='DrivingLicenseCredential'
def body(code, value, expected=200):
    if code != expected: raise ValueError(f'HTTP {code}, expected {expected}')
    if not isinstance(value,dict) or value.get('errors'): raise ValueError('invalid object or error envelope')
    return value

def health(code,m):
    m=body(code,m)
    if m.get('status')!='UP': raise ValueError('health is not UP')

def metadata(code,m):
    m=body(code,m)
    for key,want in {'credential_issuer':BASE,'credential_endpoint':BASE+'/v1/certify/issuance/credential','nonce_endpoint':BASE+'/v1/certify/nonce'}.items():
        if m.get(key)!=want: raise ValueError('unexpected '+key)
    configs=m.get('credential_configurations_supported')
    if not isinstance(configs,dict) or not configs: raise ValueError('missing/nonobject/empty Final configurations')
    c=configs.get(CONFIG)
    if not isinstance(c,dict) or c.get('format')!='mso_mdoc' or c.get('doctype')!='org.iso.18013.5.1.mDL': raise ValueError('wrong mDL config')
    if c.get('scope')!='sample_vc_mdoc' or 'ES256' not in c.get('credential_signing_alg_values_supported',[]): raise ValueError('wrong scope/signing algorithm')
    proofs=c.get('proof_types_supported')
    if not isinstance(proofs,dict) or 'ES256' not in proofs.get('jwt',{}).get('proof_signing_alg_values_supported',[]): raise ValueError('missing ES256 proof')
    return c

def nonce(code,m,headers):
    m=body(code,m)
    if not isinstance(m.get('c_nonce'),str) or not m['c_nonce'].strip(): raise ValueError('missing nonce')
    if 'no-store' not in headers.get('Cache-Control','').lower(): raise ValueError('missing no-store')
