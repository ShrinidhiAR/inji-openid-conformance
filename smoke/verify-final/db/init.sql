\set ON_ERROR_STOP on
CREATE SCHEMA verify;
SET search_path TO verify;
\i /bundle/verify-authorization_request_details.sql
\i /bundle/verify-presentation_definition.sql
\i /bundle/verify-vc_submission.sql
\i /bundle/verify-vp_submission.sql
