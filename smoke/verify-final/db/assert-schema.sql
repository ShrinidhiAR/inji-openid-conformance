\set ON_ERROR_STOP on
-- Read-only assertions against fresh local Verify schema, no ALTER/repair.
DO $$
DECLARE missing_count integer;
BEGIN
 SELECT count(*) INTO missing_count FROM (VALUES
 ('authorization_request_details','request_id','character varying','NO'),
 ('authorization_request_details','transaction_id','character varying','NO'),
 ('authorization_request_details','authorization_details','text','NO'),
 ('authorization_request_details','expires_at','bigint','NO'),
 ('presentation_definition','id','character varying','NO'),
 ('presentation_definition','input_descriptors','text','NO'),
 ('presentation_definition','name','character varying','YES'),
 ('presentation_definition','purpose','character varying','YES'),
 ('presentation_definition','vp_format','text','YES'),
 ('presentation_definition','submission_requirements','text','YES'),
 ('vc_submission','transaction_id','character varying','NO'),
 ('vc_submission','vc','text','NO'),
 ('vp_submission','request_id','character varying','NO'),
 ('vp_submission','vp_token','character varying','YES'),
 ('vp_submission','presentation_submission','text','YES'),
 ('vp_submission','error','character varying','YES'),
 ('vp_submission','error_description','character varying','YES'),
 ('vp_submission','response_code','character varying','YES'),
 ('vp_submission','response_code_expiry_at','timestamp with time zone','YES'),
 ('vp_submission','response_code_used','boolean','YES')
 ) AS expected(table_name,column_name,data_type,is_nullable)
 LEFT JOIN information_schema.columns actual ON actual.table_schema='verify'
 AND actual.table_name=expected.table_name AND actual.column_name=expected.column_name
 AND actual.data_type=expected.data_type AND actual.is_nullable=expected.is_nullable
 WHERE actual.column_name IS NULL;
 IF missing_count<>0 THEN RAISE EXCEPTION 'Verify schema contract mismatch: % columns',missing_count; END IF;
 IF NOT EXISTS(SELECT 1 FROM information_schema.table_constraints WHERE table_schema='verify' AND table_name='vp_submission' AND constraint_name='pk_vp_submission_request_id' AND constraint_type='PRIMARY KEY')
 OR NOT EXISTS(SELECT 1 FROM information_schema.table_constraints WHERE table_schema='verify' AND table_name='vp_submission' AND constraint_name='uq_vp_submission_response_code' AND constraint_type='UNIQUE') THEN RAISE EXCEPTION 'Verify submission constraints missing'; END IF;
 IF NOT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='verify' AND table_name='vp_submission' AND column_name='response_code_used' AND column_default='false') THEN RAISE EXCEPTION 'Verify response_code_used default mismatch'; END IF;
END $$;
