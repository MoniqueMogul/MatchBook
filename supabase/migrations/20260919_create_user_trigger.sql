CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_first_name TEXT;
    v_last_name TEXT;
BEGIN
    v_first_name := NULLIF(
        TRIM(NEW.raw_user_meta_data ->> 'first_name'),
        ''
    );

    v_last_name := NULLIF(
        TRIM(NEW.raw_user_meta_data ->> 'last_name'),
        ''
    );

    IF v_first_name IS NULL OR v_last_name IS NULL THEN
        RAISE EXCEPTION
            'first_name and last_name are required';
    END IF;

    INSERT INTO public.users (
        id,
        email,
        phone,
        first_name,
        last_name,
        status,
        verification_status
    )
    VALUES (
        NEW.id,
        NEW.email,
        NEW.phone,
        v_first_name,
        v_last_name,
        'active',
        'unverified'
    )
    ON CONFLICT (id) DO NOTHING;

    RETURN NEW;
END;
$$;


DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;


CREATE TRIGGER on_auth_user_created
AFTER INSERT ON auth.users
FOR EACH ROW
EXECUTE FUNCTION public.handle_new_user();