"""Strict alpha Final request/response. No protocol values retained in exceptions."""
def credential_response(status,b):
    if status!=200 or not isinstance(b,dict) or b.get('errors') or b.get('error'):raise ValueError('credential protocol failure')
    cs=b.get('credentials')
    if not isinstance(cs,list) or len(cs)!=1 or not isinstance(cs[0],dict):raise ValueError('expected one credential object')
    c=cs[0].get('credential')
    if not isinstance(c,str) or not c:raise ValueError('missing credential string')
    if 'credential' in b:raise ValueError('unexpected legacy response shape')
    return c

def proof_request(configuration_id,proof):
    if not configuration_id or not isinstance(proof,str) or proof.count('.')!=2:raise ValueError('invalid proof request')
    return {'credential_configuration_id':configuration_id,'proofs':{'jwt':[proof]}}
