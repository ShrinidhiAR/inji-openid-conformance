import com.nimbusds.jose.*;import com.nimbusds.jose.crypto.*;import com.nimbusds.jose.jwk.*;import com.nimbusds.jose.jwk.gen.*;import com.nimbusds.jwt.*;import io.mosip.certify.proof.JwtProofValidator;import java.util.*;
public class ProofContract{
 static String make(ECKey key,ECKey header,String typ,String aud,String nonce,String iss,boolean ambiguous)throws Exception{
  var h=new JWSHeader.Builder(JWSAlgorithm.ES256).type(new JOSEObjectType(typ)).jwk(header);if(ambiguous)h.keyID("did:jwk:invalid");
  var c=new JWTClaimsSet.Builder().audience(aud).issueTime(new Date()).claim("nonce",nonce);if(iss!=null)c.issuer(iss);
  var jwt=new SignedJWT(h.build(),c.build());jwt.sign(new ECDSASigner(key));return jwt.serialize();
 }
 public static void main(String[] args)throws Exception{
  var v=new JwtProofValidator();var f=JwtProofValidator.class.getDeclaredField("credentialIdentifier");f.setAccessible(true);f.set(v,"http://localhost:8099");
  var key=new ECKeyGenerator(Curve.P_256).generate();var other=new ECKeyGenerator(Curve.P_256).generate();
  Map<String,Object> config=Map.of("jwt",Map.of("proof_signing_alg_values_supported",List.of("ES256")));
  String[][] cases={{"openid4vci-proof+jwt","http://localhost:8099","fresh-fixture-nonce","wallet"},{"wrong","http://localhost:8099","fresh-fixture-nonce","wallet"},{"openid4vci-proof+jwt","wrong-aud","fresh-fixture-nonce","wallet"},{"openid4vci-proof+jwt","http://localhost:8099","wrong-nonce","wallet"},{"openid4vci-proof+jwt","http://localhost:8099","fresh-fixture-nonce","other-client"}};
  int i=0;for(var c:cases){boolean got=v.validate("wallet","fresh-fixture-nonce",make(key,key.toPublicJWK(),c[0],c[1],c[2],c[3],false),config);if(got!=(i==0))throw new AssertionError("case"+i);System.out.println("PASS actual alpha JwtProofValidator case"+i+" accepted="+got);i++;}
  // Build an actual signed private-JWK header without Nimbus Builder's guard.
  var rawHeader=new java.util.HashMap<String,Object>();rawHeader.put("alg","ES256");rawHeader.put("typ","openid4vci-proof+jwt");rawHeader.put("jwk",key.toJSONObject());
  String hh=com.nimbusds.jose.util.Base64URL.encode(new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(rawHeader)).toString();
  String cc=com.nimbusds.jose.util.Base64URL.encode(new JWTClaimsSet.Builder().audience("http://localhost:8099").issueTime(new Date()).claim("nonce","fresh-fixture-nonce").issuer("wallet").build().toString()).toString();
  var ss=new ECDSASigner(key).sign(new JWSHeader(JWSAlgorithm.ES256),(hh+"."+cc).getBytes(java.nio.charset.StandardCharsets.US_ASCII));
  boolean priv=v.validate("wallet","fresh-fixture-nonce",hh+"."+cc+"."+ss,config);if(priv)throw new AssertionError("private JWK accepted");System.out.println("PASS actual alpha rejects private JWK header");
  boolean mismatch=v.validate("wallet","fresh-fixture-nonce",make(key,other.toPublicJWK(),"openid4vci-proof+jwt","http://localhost:8099","fresh-fixture-nonce","wallet",false),config);if(mismatch)throw new AssertionError("signature mismatch accepted");System.out.println("PASS actual alpha rejects mismatched signature/header key");
  boolean ambiguous=v.validate("wallet","fresh-fixture-nonce",make(key,key.toPublicJWK(),"openid4vci-proof+jwt","http://localhost:8099","fresh-fixture-nonce","wallet",true),config);if(ambiguous)throw new AssertionError("ambiguous accepted");System.out.println("PASS actual alpha rejects simultaneous jwk+kid");
 }
}
