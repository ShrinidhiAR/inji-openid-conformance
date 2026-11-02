import io.mosip.esignet.core.validator.RedirectURLValidator;
public class RedirectContract {
 public static void main(String[] args) {
  var validator=new RedirectURLValidator();
  if(validator.isValid("https://suite.local.test:8443/test/a/alpha-official/callback",null))throw new AssertionError("negative callback must be rejected");
  if(!validator.isValid(args[0],null))throw new AssertionError("integrated callback rejected");
  System.out.println("ACTUAL_ESIGNET_REDIRECT_VALIDATOR_POSITIVE_NEGATIVE_PASS");
 }
}
