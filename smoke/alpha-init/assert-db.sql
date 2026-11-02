DO $$ BEGIN
IF (SELECT count(*) FROM certify.key_policy_def WHERE is_active AND app_id IN
('ROOT','CERTIFY_SERVICE','CERTIFY_PARTNER','CERTIFY_VC_SIGN_RSA','BASE','CERTIFY_VC_SIGN_ED25519','CERTIFY_VC_SIGN_EC_K1','CERTIFY_VC_SIGN_EC_R1')) <> 8 THEN RAISE EXCEPTION 'missing key policies'; END IF;
IF (SELECT count(*) FROM information_schema.tables WHERE table_schema='certify') <> 16 THEN RAISE EXCEPTION 'expected 16 release tables'; END IF;
IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='certify' AND table_name='credential_config' AND column_name='claims') THEN RAISE EXCEPTION 'alpha claims column absent'; END IF;
END $$;
