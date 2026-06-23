-- Run this in the Supabase SQL editor after creating the 'documents' storage bucket

-- Create the documents bucket (if not already created via dashboard)
INSERT INTO storage.buckets (id, name, public)
VALUES ('documents', 'documents', false)
ON CONFLICT DO NOTHING;

-- Storage RLS policies
-- Users can upload to their own folder: documents/{user_id}/...
CREATE POLICY "Users can upload own documents"
    ON storage.objects FOR INSERT
    WITH CHECK (
        bucket_id = 'documents'
        AND auth.uid()::text = (storage.foldername(name))[1]
    );

-- Users can read their own files
CREATE POLICY "Users can read own documents"
    ON storage.objects FOR SELECT
    USING (
        bucket_id = 'documents'
        AND auth.uid()::text = (storage.foldername(name))[1]
    );

-- Users can delete their own files
CREATE POLICY "Users can delete own documents"
    ON storage.objects FOR DELETE
    USING (
        bucket_id = 'documents'
        AND auth.uid()::text = (storage.foldername(name))[1]
    );

-- Service role has full access (used by FastAPI backend)
CREATE POLICY "Service role full access"
    ON storage.objects FOR ALL
    USING (auth.role() = 'service_role');