"""Official event allowlist only. Never raw URL, headers, body or error message."""
from tls_config import CERTIFY
TARGET=CERTIFY+'/.well-known/openid-credential-issuer'
CAUSES={'org.springframework.web.client.ResourceAccessException','org.springframework.web.client.RestClientException','org.springframework.web.client.HttpClientErrorException$NotFound','org.springframework.web.client.HttpClientErrorException','org.springframework.web.client.HttpServerErrorException','java.net.UnknownHostException','java.net.ConnectException','java.net.SocketTimeoutException','javax.net.ssl.SSLHandshakeException','javax.net.ssl.SSLException','org.apache.hc.client5.http.ConnectTimeoutException','org.apache.hc.client5.http.HttpHostConnectException'}
def project(events):
 out=[]
 for e in events:
  if not isinstance(e,dict) or e.get('src')!='VCIGetDynamicCredentialIssuerMetadata':continue
  safe={'source':'VCIGetDynamicCredentialIssuerMetadata'}
  # Controlled source key, never copy a returned destination into output.
  url=e.get('credential_issuer_metadata_endpoint_url')
  if url is not None:safe['target_matches_expected']=url==TARGET
  if url==TARGET:safe['target_origin']='certify';safe['target_path']='/.well-known/openid-credential-issuer'
  for key in ('error_class','cause_class'):
   if key in e:safe[key]=e[key] if e[key] in CAUSES else '<other>'
  if isinstance(e.get('status'),int) and 100<=e['status']<=599:safe['http']=e['status']
  # Spring may throw before the status is directly recorded. Exact exception
  # class, not message, establishes only this narrow response category.
  if e.get('error_class')=='org.springframework.web.client.HttpClientErrorException$NotFound':safe['http_category']='not_found'
  if len(safe)>1 and safe not in out:out.append(safe)
 return out
