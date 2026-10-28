import com.fasterxml.jackson.databind.*;
import jakarta.validation.*;
import io.mosip.esignet.core.dto.*;
import io.mosip.esignet.core.util.*;
import org.springframework.core.env.*;
import java.nio.file.*;
import java.util.*;
public class EsignetDtoContract{
 static void set(Object o,String n,Object v)throws Exception{var f=o.getClass().getDeclaredField(n);f.setAccessible(true);f.set(o,v);}
 public static void main(String[]args)throws Exception{
 var env=new StandardEnvironment();var props=new HashMap<String,Object>();props.put("mosip.esignet.auth-challenge.PWD.format","alpha-numeric");props.put("mosip.esignet.auth-challenge.PWD.min-length","8");props.put("mosip.esignet.auth-challenge.PWD.max-length","30");env.getPropertySources().addFirst(new MapPropertySource("controlled deployed values",props));
 ConstraintValidatorFactory factory=new ConstraintValidatorFactory(){public <T extends ConstraintValidator<?,?>> T getInstance(Class<T> c){try{
 var o=c.getDeclaredConstructor().newInstance();switch(c.getSimpleName()){
 case "IdFormatValidator":set(o,"supportedRegex","\\S*");break;
 case "RequestTimeValidator":set(o,"leewayInMinutes",2);break;
 case "OIDCClaimValidator":set(o,"discoveryMap",Map.of("claims_supported",List.of("name","address","gender","birthdate","picture","email","phone_number","individual_id","phone_number_verified","registration_type","updated_at")));break;
 case "OIDCGrantTypeValidator":set(o,"supportedGrantTypes",List.of("authorization_code"));break;
 case "OIDCClientAuthValidator":set(o,"supportedClientAuthMethods",List.of("private_key_jwt"));break;
 case "AuthContextRefValidator":set(o,"acrUtil",new AuthenticationContextClassRefUtil(){public Set<String> getSupportedACRValues(){return Set.of("mosip:idp:acr:password","mosip:idp:acr:static-code","mosip:idp:acr:generated-code");}});break;
 case "AuthChallengeFactorFormatValidator":set(o,"environment",env);break;
 }return o;}catch(Exception e){throw new RuntimeException(c.getSimpleName(),e);}}public void releaseInstance(ConstraintValidator<?,?>o){}};
 var validator=Validation.byDefaultProvider().configure().constraintValidatorFactory(factory).buildValidatorFactory().getValidator();var mapper=new ObjectMapper();var raw=mapper.readTree(Files.readString(java.nio.file.Path.of(args[0])));var type=mapper.getTypeFactory().constructParametricType(RequestWrapper.class,ClientDetailCreateRequestV2.class);
 Object integrated=mapper.readerFor(type).readValue(raw);var iv=validator.validate(integrated);System.out.println("integrated_complete_request violations="+iv.size());if(!iv.isEmpty())throw new AssertionError("integrated request rejected");
 for(String host:List.of("suite.local.test","suite.localhost","suite")){
 var b=raw.deepCopy();((com.fasterxml.jackson.databind.node.ObjectNode)b).put("requestTime",java.time.LocalDateTime.now(java.time.ZoneOffset.UTC).format(java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'")));((com.fasterxml.jackson.databind.node.ObjectNode)b.get("request")).putArray("redirectUris").add("https://"+host+":8443/test/a/alpha-official/callback");Object dto=mapper.readerFor(type).readValue(b);var violations=validator.validate(dto);System.out.println("controlled_host="+host+" violations="+violations.size());for(var v:violations)System.out.println(v.getPropertyPath()+" code="+v.getMessageTemplate());
 }
 for(var row:mapper.readTree(Files.readString(java.nio.file.Path.of(args[1])))){
 var operation=row.get("operation").asText();Class klass=switch(operation){case "par-oauth-details"->PushedOAuthDetailRequest.class;case "authenticate"->AuthRequest.class;case "auth-code"->AuthCodeRequest.class;default->throw new IllegalArgumentException();};var body=row.get("body").deepCopy();((com.fasterxml.jackson.databind.node.ObjectNode)body).put("requestTime",java.time.LocalDateTime.now(java.time.ZoneOffset.UTC).format(java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'")));var t=mapper.getTypeFactory().constructParametricType(RequestWrapper.class,klass);Object dto=mapper.readerFor(t).readValue(body);var violations=validator.validate(dto);System.out.println("downstream="+operation+" violations="+violations.size());for(var v:violations)System.out.println(v.getPropertyPath()+" code="+v.getMessageTemplate());
 }
 var pub=mapper.convertValue(raw.get("request").get("publicKey"),Map.class);IdentityProviderUtil.getJWKString(pub);System.out.println("public_jwk_parse=PASS");
 }
}
