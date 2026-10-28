import com.fasterxml.jackson.databind.*;
import jakarta.validation.*;
import io.mosip.certify.core.dto.*;
public class Contract{
 public static void main(String[] a)throws Exception{
 ObjectMapper m=new ObjectMapper();Validator v=Validation.buildDefaultValidatorFactory().getValidator();
 String[] bodies={"{\"credential_configuration_id\":\"DrivingLicenseCredential\",\"proofs\":{\"jwt\":[\"shape-only-not-a-signed-proof\"]}}","{\"credential_configuration_id\":\"DrivingLicenseCredential\",\"proofs\":{\"jwt\":[]}}","{\"credential_configuration_id\":\"DrivingLicenseCredential\",\"proofs\":{\"jwt\":[\"\"]}}","{\"credential_configuration_id\":\"DrivingLicenseCredential\",\"proofs\":{}}","{\"proofs\":{\"jwt\":[\"x\"]}}","{\"format\":\"mso_mdoc\",\"doctype\":\"org.iso.18013.5.1.mDL\",\"proof\":{\"proof_type\":\"jwt\",\"jwt\":\"x\"}}"};
 int i=0;for(String b:bodies){boolean ok;try{ok=v.validate(m.readValue(b,CredentialRequest.class)).isEmpty();}catch(Exception e){ok=false;}if(ok!=(i==0))throw new AssertionError("case"+i);System.out.println("PASS actual alpha DTO case"+i+" accepted="+ok);i++;}
 var r=m.readValue("{\"credentials\":[{\"credential\":\"shape-only-cbor-string\"}]}",CredentialResponse.class);if(r.getCredentials().size()!=1)throw new AssertionError();System.out.println("PASS actual alpha response DTO credentials[] wrapper");
 }
}
