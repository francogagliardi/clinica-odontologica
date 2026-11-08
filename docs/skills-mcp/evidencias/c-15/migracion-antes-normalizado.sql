--
-- PostgreSQL database dump
--


-- Dumped from database version 17.10
-- Dumped by pg_dump version 17.10

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: btree_gist; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public;


--
-- Name: EXTENSION btree_gist; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION btree_gist IS 'support for indexing common datatypes in GiST';


--
-- Name: consentimientos_append_only(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.consentimientos_append_only() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    RAISE EXCEPTION
        'consentimientos es append-only (RN-CL-04): % no permitido', TG_OP
        USING ERRCODE = 'P0001';
END;
$$;


--
-- Name: evoluciones_inmutabilidad(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.evoluciones_inmutabilidad() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.firmada THEN
            RAISE EXCEPTION
                'Una evolución firmada es inmutable (RN-CL-04): DELETE no permitido'
                USING ERRCODE = 'P0001';
        END IF;
        RETURN OLD;
    END IF;

    IF OLD.firmada THEN
        RAISE EXCEPTION
            'Una evolución firmada es inmutable (RN-CL-04): UPDATE no permitido'
            USING ERRCODE = 'P0001';
    END IF;

    IF NEW.firmada THEN
        IF NEW.historia_id IS DISTINCT FROM OLD.historia_id
           OR NEW.profesional_id IS DISTINCT FROM OLD.profesional_id
           OR NEW.creado_por IS DISTINCT FROM OLD.creado_por
           OR NEW.fecha IS DISTINCT FROM OLD.fecha
           OR NEW.texto IS DISTINCT FROM OLD.texto
           OR NEW.rectifica_a IS DISTINCT FROM OLD.rectifica_a THEN
            RAISE EXCEPTION
                'La firma no puede modificar el contenido (RN-CL-04)'
                USING ERRCODE = 'P0001';
        END IF;
        IF NEW.firmada_por IS NULL OR NEW.fecha_firma IS NULL THEN
            RAISE EXCEPTION
                'La firma exige firmada_por y fecha_firma (RN-CL-04)'
                USING ERRCODE = 'P0001';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.historia_id IS DISTINCT FROM OLD.historia_id
       OR NEW.profesional_id IS DISTINCT FROM OLD.profesional_id
       OR NEW.creado_por IS DISTINCT FROM OLD.creado_por
       OR NEW.fecha IS DISTINCT FROM OLD.fecha
       OR NEW.rectifica_a IS DISTINCT FROM OLD.rectifica_a THEN
        RAISE EXCEPTION
            'El borrador no puede cambiar historia, profesional, autor, '
            'fecha ni rectificación'
            USING ERRCODE = 'P0001';
    END IF;
    RETURN NEW;
END;
$$;


--
-- Name: hallazgos_dentales_append_only(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.hallazgos_dentales_append_only() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    RAISE EXCEPTION
        'hallazgos_dentales es append-only (RN-CL-04): % no permitido', TG_OP
        USING ERRCODE = 'P0001';
END;
$$;


--
-- Name: odontogramas_append_only(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.odontogramas_append_only() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    RAISE EXCEPTION
        'odontogramas es append-only (RN-CL-04): % no permitido', TG_OP
        USING ERRCODE = 'P0001';
END;
$$;


--
-- Name: registro_auditoria_append_only(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.registro_auditoria_append_only() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    RAISE EXCEPTION
        'registro_auditoria es append-only (RN-SE-02): % no permitido', TG_OP
        USING ERRCODE = 'P0001';
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: adjuntos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.adjuntos (
    id uuid NOT NULL,
    historia_id uuid NOT NULL,
    nombre character varying(255) NOT NULL,
    mime character varying(60) NOT NULL,
    tamano integer NOT NULL,
    contenido bytea NOT NULL,
    subido_por uuid NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_adjuntos_baja_logica_coherente CHECK (((deleted_at IS NULL) = is_active)),
    CONSTRAINT ck_adjuntos_mime_permitido CHECK (((mime)::text = ANY ((ARRAY['image/jpeg'::character varying, 'image/png'::character varying, 'image/webp'::character varying, 'application/pdf'::character varying])::text[]))),
    CONSTRAINT ck_adjuntos_nombre_saneado CHECK (((btrim((nombre)::text) <> ''::text) AND ((nombre)::text !~~ '%..%'::text) AND ((nombre)::text !~ '[/\\]'::text))),
    CONSTRAINT ck_adjuntos_tamano_coherente CHECK ((tamano = octet_length(contenido))),
    CONSTRAINT ck_adjuntos_tamano_valido CHECK (((tamano > 0) AND (tamano <= 5242880)))
);


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: bloqueos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bloqueos (
    id uuid NOT NULL,
    profesional_id uuid,
    sillon_id uuid,
    desde timestamp with time zone NOT NULL,
    hasta timestamp with time zone NOT NULL,
    motivo character varying(200) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_bloqueos_baja_logica_coherente CHECK (((deleted_at IS NULL) = is_active)),
    CONSTRAINT ck_bloqueos_rango_coherente CHECK ((hasta > desde)),
    CONSTRAINT ck_bloqueos_recurso_exclusivo CHECK (((profesional_id IS NOT NULL) <> (sillon_id IS NOT NULL)))
);


--
-- Name: cajas_diarias; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cajas_diarias (
    id uuid NOT NULL,
    consultorio_id uuid NOT NULL,
    fecha date NOT NULL,
    estado character varying(20) DEFAULT 'abierta'::character varying NOT NULL,
    monto_apertura numeric(12,2) NOT NULL,
    monto_sistema_efectivo numeric(12,2),
    monto_contado numeric(12,2),
    diferencia numeric(12,2),
    cerrada_por uuid,
    cerrada_at timestamp with time zone,
    observaciones character varying(500),
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_cajas_diarias_baja_logica_coherente CHECK (((deleted_at IS NULL) = is_active)),
    CONSTRAINT ck_cajas_diarias_cierre_coherente CHECK (((((estado)::text = 'abierta'::text) AND (monto_sistema_efectivo IS NULL) AND (monto_contado IS NULL) AND (diferencia IS NULL) AND (cerrada_por IS NULL) AND (cerrada_at IS NULL)) OR (((estado)::text = 'cerrada'::text) AND (monto_sistema_efectivo IS NOT NULL) AND (monto_contado IS NOT NULL) AND (diferencia = (monto_contado - monto_sistema_efectivo)) AND (cerrada_por IS NOT NULL) AND (cerrada_at IS NOT NULL)))),
    CONSTRAINT ck_cajas_diarias_estado_valido CHECK (((estado)::text = ANY ((ARRAY['abierta'::character varying, 'cerrada'::character varying])::text[]))),
    CONSTRAINT ck_cajas_diarias_monto_apertura_no_negativo CHECK ((monto_apertura >= (0)::numeric))
);


--
-- Name: cobros; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cobros (
    id uuid NOT NULL,
    consultorio_id uuid NOT NULL,
    paciente_id uuid NOT NULL,
    turno_id uuid,
    presupuesto_id uuid,
    creado_por uuid,
    tipo character varying(20) NOT NULL,
    medio character varying(20) NOT NULL,
    estado character varying(20) DEFAULT 'pendiente'::character varying NOT NULL,
    monto numeric(12,2) NOT NULL,
    proveedor_pago_id character varying(100),
    proveedor_preferencia_id character varying(100),
    link_pago text,
    fecha_operacion date NOT NULL,
    fecha_conciliacion timestamp with time zone,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_cobros_baja_logica_coherente CHECK (((deleted_at IS NULL) = is_active)),
    CONSTRAINT ck_cobros_efectivo_no_pendiente CHECK ((((medio)::text <> 'efectivo'::text) OR ((estado)::text <> 'pendiente'::text))),
    CONSTRAINT ck_cobros_estado_valido CHECK (((estado)::text = ANY ((ARRAY['pendiente'::character varying, 'aprobado'::character varying, 'rechazado'::character varying, 'reembolsado'::character varying, 'perdido'::character varying])::text[]))),
    CONSTRAINT ck_cobros_medio_valido CHECK (((medio)::text = ANY ((ARRAY['efectivo'::character varying, 'mercadopago'::character varying])::text[]))),
    CONSTRAINT ck_cobros_monto_positivo CHECK ((monto > (0)::numeric)),
    CONSTRAINT ck_cobros_proveedor_pago_solo_mp CHECK (((proveedor_pago_id IS NULL) OR ((medio)::text = 'mercadopago'::text))),
    CONSTRAINT ck_cobros_referencias_coherentes CHECK (((((tipo)::text = 'sena'::text) AND (turno_id IS NOT NULL) AND (presupuesto_id IS NULL)) OR (((tipo)::text = 'tratamiento'::text) AND (presupuesto_id IS NOT NULL) AND (turno_id IS NULL)) OR (((tipo)::text = 'otro'::text) AND (turno_id IS NULL) AND (presupuesto_id IS NULL)))),
    CONSTRAINT ck_cobros_tipo_valido CHECK (((tipo)::text = ANY ((ARRAY['sena'::character varying, 'tratamiento'::character varying, 'otro'::character varying])::text[])))
);


--
-- Name: comprobantes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.comprobantes (
    id uuid NOT NULL,
    consultorio_id uuid NOT NULL,
    cobro_id uuid NOT NULL,
    paciente_id uuid NOT NULL,
    tipo character varying(1) NOT NULL,
    ambiente character varying(20) DEFAULT 'homologacion'::character varying NOT NULL,
    estado character varying(20) DEFAULT 'pendiente'::character varying NOT NULL,
    numero_interno bigint NOT NULL,
    punto_venta integer NOT NULL,
    numero_fiscal bigint,
    cae character varying(14),
    cae_vencimiento date,
    qr_interno text NOT NULL,
    qr_fiscal text,
    receptor_nombre character varying(200) NOT NULL,
    receptor_documento character varying(20) NOT NULL,
    receptor_tipo_documento character varying(10) DEFAULT 'DNI'::character varying NOT NULL,
    condicion_fiscal_receptor character varying(30) DEFAULT 'consumidor_final'::character varying NOT NULL,
    condicion_fiscal_emisor character varying(30) NOT NULL,
    importe_total numeric(12,2) NOT NULL,
    fecha_emision date NOT NULL,
    fecha_emision_fiscal timestamp with time zone,
    intentos integer DEFAULT 0 NOT NULL,
    proximo_intento timestamp with time zone,
    ultimo_error text,
    claim_token uuid,
    reclamado_at timestamp with time zone,
    payload_envio jsonb,
    respuesta_proveedor jsonb,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_comprobantes_ambiente_valido CHECK (((ambiente)::text = 'homologacion'::text)),
    CONSTRAINT ck_comprobantes_baja_logica_coherente CHECK (((deleted_at IS NULL) = is_active)),
    CONSTRAINT ck_comprobantes_cae_formato CHECK (((cae IS NULL) OR ((cae)::text ~ '^[0-9]{14}$'::text))),
    CONSTRAINT ck_comprobantes_estado_fiscal_coherente CHECK (((((estado)::text = 'emitido'::text) AND (cae IS NOT NULL) AND (cae_vencimiento IS NOT NULL) AND (numero_fiscal IS NOT NULL) AND (qr_fiscal IS NOT NULL) AND (fecha_emision_fiscal IS NOT NULL)) OR (((estado)::text = ANY ((ARRAY['pendiente'::character varying, 'fallido'::character varying])::text[])) AND (cae IS NULL) AND (cae_vencimiento IS NULL) AND (numero_fiscal IS NULL) AND (qr_fiscal IS NULL) AND (fecha_emision_fiscal IS NULL)))),
    CONSTRAINT ck_comprobantes_estado_valido CHECK (((estado)::text = ANY ((ARRAY['pendiente'::character varying, 'emitido'::character varying, 'fallido'::character varying])::text[]))),
    CONSTRAINT ck_comprobantes_fallido_con_error CHECK ((((estado)::text <> 'fallido'::text) OR (ultimo_error IS NOT NULL))),
    CONSTRAINT ck_comprobantes_importe_positivo CHECK ((importe_total > (0)::numeric)),
    CONSTRAINT ck_comprobantes_intentos_no_negativos CHECK ((intentos >= 0)),
    CONSTRAINT ck_comprobantes_numero_fiscal_positivo CHECK (((numero_fiscal IS NULL) OR (numero_fiscal > 0))),
    CONSTRAINT ck_comprobantes_numero_interno_positivo CHECK ((numero_interno > 0)),
    CONSTRAINT ck_comprobantes_punto_venta_positivo CHECK ((punto_venta > 0)),
    CONSTRAINT ck_comprobantes_tipo_valido CHECK (((tipo)::text = ANY ((ARRAY['B'::character varying, 'C'::character varying])::text[])))
);


--
-- Name: comprobantes_envios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.comprobantes_envios (
    id uuid NOT NULL,
    comprobante_id uuid NOT NULL,
    canal character varying(20) NOT NULL,
    destino character varying(120) NOT NULL,
    estado character varying(20) DEFAULT 'registrado'::character varying NOT NULL,
    proveedor_mensaje_id character varying(100),
    error text,
    creado_por uuid,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_comprobantes_envios_baja_logica_coherente CHECK (((deleted_at IS NULL) = is_active)),
    CONSTRAINT ck_comprobantes_envios_canal_valido CHECK (((canal)::text = 'whatsapp'::text)),
    CONSTRAINT ck_comprobantes_envios_destino_no_vacio CHECK ((btrim((destino)::text) <> ''::text)),
    CONSTRAINT ck_comprobantes_envios_estado_valido CHECK (((estado)::text = ANY ((ARRAY['registrado'::character varying, 'fallido'::character varying])::text[])))
);


--
-- Name: consentimientos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.consentimientos (
    id uuid NOT NULL,
    consultorio_id uuid NOT NULL,
    paciente_id uuid NOT NULL,
    tipo character varying(40) NOT NULL,
    texto_version character varying(20) NOT NULL,
    texto_hash character varying(64) NOT NULL,
    firma_ref character varying(80) NOT NULL,
    fecha timestamp with time zone DEFAULT now() NOT NULL,
    registrado_por uuid NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_consentimientos_baja_logica_coherente CHECK (((deleted_at IS NULL) = is_active)),
    CONSTRAINT ck_consentimientos_firma_ref_formato CHECK (((firma_ref)::text ~ '^sha256:[0-9a-f]{64}$'::text)),
    CONSTRAINT ck_consentimientos_texto_hash_formato CHECK (((texto_hash)::text ~ '^[0-9a-f]{64}$'::text)),
    CONSTRAINT ck_consentimientos_tipo_valido CHECK (((tipo)::text = 'procedimiento_invasivo'::text))
);


--
-- Name: consultorios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.consultorios (
    id uuid NOT NULL,
    nombre character varying(120) NOT NULL,
    slug character varying(60) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    plazo_cancelacion_horas integer DEFAULT 24 NOT NULL,
    CONSTRAINT ck_consultorios_baja_logica_coherente CHECK (((deleted_at IS NULL) = is_active)),
    CONSTRAINT ck_consultorios_plazo_cancelacion_valido CHECK (((plazo_cancelacion_horas >= 0) AND (plazo_cancelacion_horas <= 720)))
);


--
-- Name: entradas_lista_espera; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.entradas_lista_espera (
    id uuid NOT NULL,
    consultorio_id uuid NOT NULL,
    paciente_id uuid NOT NULL,
    prestacion_id uuid NOT NULL,
    profesional_id uuid,
    orden bigint NOT NULL,
    estado character varying(20) DEFAULT 'pendiente'::character varying NOT NULL,
    oferta_profesional_id uuid,
    oferta_sillon_id uuid,
    oferta_inicio timestamp with time zone,
    oferta_fin timestamp with time zone,
    oferta_expira_en timestamp with time zone,
    turno_id uuid,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_entradas_lista_espera_baja_logica_coherente CHECK (((deleted_at IS NULL) = is_active)),
    CONSTRAINT ck_entradas_lista_espera_conversion_con_turno CHECK ((((estado)::text <> 'convertido'::text) OR (turno_id IS NOT NULL))),
    CONSTRAINT ck_entradas_lista_espera_estado_valido CHECK (((estado)::text = ANY ((ARRAY['pendiente'::character varying, 'ofrecido'::character varying, 'convertido'::character varying, 'vencido'::character varying])::text[]))),
    CONSTRAINT ck_entradas_lista_espera_oferta_completa CHECK ((((estado)::text <> 'ofrecido'::text) OR ((oferta_inicio IS NOT NULL) AND (oferta_fin > oferta_inicio) AND (oferta_profesional_id IS NOT NULL) AND (oferta_sillon_id IS NOT NULL) AND (oferta_expira_en IS NOT NULL)))),
    CONSTRAINT ck_entradas_lista_espera_sin_retencion_fuera_de_oferta CHECK ((((estado)::text = 'ofrecido'::text) OR ((oferta_inicio IS NULL) AND (oferta_fin IS NULL) AND (oferta_profesional_id IS NULL) AND (oferta_sillon_id IS NULL) AND (oferta_expira_en IS NULL))))
);


--
-- Name: entradas_lista_espera_orden_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.entradas_lista_espera ALTER COLUMN orden ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.entradas_lista_espera_orden_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: evoluciones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.evoluciones (
    id uuid NOT NULL,
    historia_id uuid NOT NULL,
    profesional_id uuid NOT NULL,
    creado_por uuid NOT NULL,
    fecha timestamp with time zone DEFAULT now() NOT NULL,
    texto text NOT NULL,
    firmada boolean DEFAULT false NOT NULL,
    firmada_por uuid,
    fecha_firma timestamp with time zone,
    rectifica_a uuid,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_evoluciones_baja_logica_coherente CHECK (((deleted_at IS NULL) = is_active)),
    CONSTRAINT ck_evoluciones_firma_coherente CHECK ((firmada = ((firmada_por IS NOT NULL) AND (fecha_firma IS NOT NULL)))),
    CONSTRAINT ck_evoluciones_texto_no_vacio CHECK ((btrim(texto) <> ''::text))
);


--
-- Name: exportaciones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.exportaciones (
    id uuid NOT NULL,
    consultorio_id uuid NOT NULL,
    solicitado_por uuid NOT NULL,
    alcance character varying(20) NOT NULL,
    paciente_id uuid,
    estado character varying(20) DEFAULT 'pendiente'::character varying NOT NULL,
    contenido bytea,
    tamano_bytes bigint,
    generada_at timestamp with time zone,
    intentos integer DEFAULT 0 NOT NULL,
    proximo_intento timestamp with time zone,
    ultimo_error text,
    claim_token uuid,
    reclamado_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_exportaciones_alcance_paciente_coherente CHECK (((((alcance)::text = 'paciente'::text) AND (paciente_id IS NOT NULL)) OR (((alcance)::text = 'consultorio'::text) AND (paciente_id IS NULL)))),
    CONSTRAINT ck_exportaciones_alcance_valido CHECK (((alcance)::text = ANY ((ARRAY['paciente'::character varying, 'consultorio'::character varying])::text[]))),
    CONSTRAINT ck_exportaciones_estado_coherente CHECK (((((estado)::text = 'lista'::text) AND (contenido IS NOT NULL) AND (tamano_bytes IS NOT NULL) AND (tamano_bytes > 0) AND (generada_at IS NOT NULL)) OR (((estado)::text = ANY ((ARRAY['pendiente'::character varying, 'generando'::character varying, 'fallida'::character varying])::text[])) AND (contenido IS NULL) AND (tamano_bytes IS NULL) AND (generada_at IS NULL)))),
    CONSTRAINT ck_exportaciones_estado_valido CHECK (((estado)::text = ANY ((ARRAY['pendiente'::character varying, 'generando'::character varying, 'lista'::character varying, 'fallida'::character varying])::text[]))),
    CONSTRAINT ck_exportaciones_fallida_con_error CHECK ((((estado)::text <> 'fallida'::text) OR (ultimo_error IS NOT NULL))),
    CONSTRAINT ck_exportaciones_intentos_no_negativos CHECK ((intentos >= 0)),
    CONSTRAINT ck_exportaciones_tamano_positivo CHECK (((tamano_bytes IS NULL) OR (tamano_bytes > 0)))
);


--
-- Name: hallazgos_dentales; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hallazgos_dentales (
    id uuid NOT NULL,
    odontograma_id uuid NOT NULL,
    pieza integer NOT NULL,
    cara character varying(20) NOT NULL,
    estado character varying(30) NOT NULL,
    diagnostico text,
    cie10 character varying(10),
    fecha date DEFAULT CURRENT_DATE NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_hallazgos_dentales_cara_valida CHECK (((cara)::text = ANY ((ARRAY['mesial'::character varying, 'distal'::character varying, 'vestibular'::character varying, 'lingual'::character varying, 'oclusal'::character varying, 'incisal'::character varying, 'completa'::character varying])::text[]))),
    CONSTRAINT ck_hallazgos_dentales_cie10_formato CHECK (((cie10 IS NULL) OR ((cie10)::text ~ '^[A-Z][0-9]{2}(\.[0-9]{1,2})?$'::text))),
    CONSTRAINT ck_hallazgos_dentales_estado_valido CHECK (((estado)::text = ANY ((ARRAY['sano'::character varying, 'caries'::character varying, 'obturacion'::character varying, 'endodoncia'::character varying, 'corona'::character varying, 'implante'::character varying, 'ausente'::character varying, 'extraccion_indicada'::character varying, 'fractura'::character varying, 'sellante'::character varying, 'protesis'::character varying])::text[]))),
    CONSTRAINT ck_hallazgos_dentales_pieza_fdi_valida CHECK ((((((pieza / 10) >= 1) AND ((pieza / 10) <= 4)) AND (((pieza % 10) >= 1) AND ((pieza % 10) <= 8))) OR ((((pieza / 10) >= 5) AND ((pieza / 10) <= 8)) AND (((pieza % 10) >= 1) AND ((pieza % 10) <= 5)))))
);


--
-- Name: historias_clinicas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.historias_clinicas (
    id uuid NOT NULL,
    consultorio_id uuid NOT NULL,
    paciente_id uuid NOT NULL,
    abierta_por uuid NOT NULL,
    fecha_apertura timestamp with time zone DEFAULT now() NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_historias_clinicas_baja_logica_coherente CHECK (((deleted_at IS NULL) = is_active))
);


--
-- Name: items_liquidacion; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.items_liquidacion (
    id uuid NOT NULL,
    liquidacion_id uuid NOT NULL,
    item_presupuesto_id uuid NOT NULL,
    presupuesto_id uuid NOT NULL,
    cobro_id uuid NOT NULL,
    prestacion_id uuid NOT NULL,
    prestacion_codigo character varying(20) NOT NULL,
    pieza integer,
    cantidad integer NOT NULL,
    cobertura_item numeric(12,2) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_items_liquidacion_baja_logica_coherente CHECK (((deleted_at IS NULL) = is_active)),
    CONSTRAINT ck_items_liquidacion_cantidad_positiva CHECK ((cantidad > 0)),
    CONSTRAINT ck_items_liquidacion_cobertura_no_negativa CHECK ((cobertura_item >= (0)::numeric))
);


--
-- Name: items_presupuesto; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.items_presupuesto (
    id uuid NOT NULL,
    presupuesto_id uuid NOT NULL,
    prestacion_id uuid NOT NULL,
    pieza integer,
    cantidad integer NOT NULL,
    precio_unitario numeric(12,2) NOT NULL,
    cobertura_item numeric(12,2) NOT NULL,
    copago_item numeric(12,2) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_items_presupuesto_baja_logica_coherente CHECK (((deleted_at IS NULL) = is_active)),
    CONSTRAINT ck_items_presupuesto_cantidad_positiva CHECK ((cantidad > 0)),
    CONSTRAINT ck_items_presupuesto_importes_no_negativos CHECK (((precio_unitario >= (0)::numeric) AND (cobertura_item >= (0)::numeric) AND (copago_item >= (0)::numeric))),
    CONSTRAINT ck_items_presupuesto_pieza_fdi_valida CHECK (((pieza IS NULL) OR (((((pieza / 10) >= 1) AND ((pieza / 10) <= 4)) AND (((pieza % 10) >= 1) AND ((pieza % 10) <= 8))) OR ((((pieza / 10) >= 5) AND ((pieza / 10) <= 8)) AND (((pieza % 10) >= 1) AND ((pieza % 10) <= 5)))))),
    CONSTRAINT ck_items_presupuesto_totales_item_coherentes CHECK (((cobertura_item + copago_item) = (precio_unitario * (cantidad)::numeric)))
);


--
-- Name: liquidaciones_obras_sociales; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.liquidaciones_obras_sociales (
    id uuid NOT NULL,
    consultorio_id uuid NOT NULL,
    obra_social_id uuid NOT NULL,
    creado_por uuid NOT NULL,
    desde date NOT NULL,
    hasta date NOT NULL,
    estado character varying(20) DEFAULT 'borrador'::character varying NOT NULL,
    total_cobertura numeric(12,2) DEFAULT 0 NOT NULL,
    cantidad_practicas integer DEFAULT 0 NOT NULL,
    observaciones character varying(500),
    cerrada_por uuid,
    cerrada_at timestamp with time zone,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_liquidaciones_obras_sociales_baja_logica_coherente CHECK (((deleted_at IS NULL) = is_active)),
    CONSTRAINT ck_liquidaciones_obras_sociales_cierre_coherente CHECK (((((estado)::text = 'borrador'::text) AND (cerrada_por IS NULL) AND (cerrada_at IS NULL)) OR (((estado)::text = 'cerrada'::text) AND (cerrada_por IS NOT NULL) AND (cerrada_at IS NOT NULL)))),
    CONSTRAINT ck_liquidaciones_obras_sociales_estado_valido CHECK (((estado)::text = ANY ((ARRAY['borrador'::character varying, 'cerrada'::character varying])::text[]))),
    CONSTRAINT ck_liquidaciones_obras_sociales_periodo_valido CHECK ((desde <= hasta)),
    CONSTRAINT ck_liquidaciones_obras_sociales_totales_no_negativos CHECK (((total_cobertura >= (0)::numeric) AND (cantidad_practicas >= 0)))
);


--
-- Name: mensajes_whatsapp; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mensajes_whatsapp (
    id uuid NOT NULL,
    recordatorio_id uuid,
    turno_id uuid,
    plantilla character varying(20) NOT NULL,
    estado_envio character varying(20) DEFAULT 'pendiente'::character varying NOT NULL,
    respuesta character varying(20) DEFAULT 'ninguna'::character varying NOT NULL,
    proveedor_mensaje_id character varying(80),
    intentos integer DEFAULT 0 NOT NULL,
    proximo_intento timestamp with time zone,
    ultimo_error text,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    lista_espera_id uuid,
    CONSTRAINT ck_mensajes_whatsapp_estado_envio_valido CHECK (((estado_envio)::text = ANY ((ARRAY['pendiente'::character varying, 'enviado'::character varying, 'fallido'::character varying])::text[]))),
    CONSTRAINT ck_mensajes_whatsapp_plantilla_valida CHECK (((plantilla)::text = ANY ((ARRAY['recordatorio'::character varying, 'confirmacion'::character varying, 'oferta_hueco'::character varying])::text[]))),
    CONSTRAINT ck_mensajes_whatsapp_respuesta_valida CHECK (((respuesta)::text = ANY ((ARRAY['ninguna'::character varying, 'confirmado'::character varying, 'cancelado'::character varying, 'reprogramado'::character varying, 'derivado'::character varying, 'aceptado'::character varying, 'rechazado'::character varying])::text[]))),
    CONSTRAINT ck_mensajes_whatsapp_turno_o_lista_espera CHECK (((turno_id IS NOT NULL) OR (lista_espera_id IS NOT NULL)))
);


--
-- Name: movimientos_caja; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.movimientos_caja (
    id uuid NOT NULL,
    caja_id uuid NOT NULL,
    tipo character varying(20) NOT NULL,
    concepto character varying(200) NOT NULL,
    monto numeric(12,2) NOT NULL,
    medio character varying(20) DEFAULT 'efectivo'::character varying NOT NULL,
    cobro_id uuid,
    creado_por uuid,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_movimientos_caja_baja_logica_coherente CHECK (((deleted_at IS NULL) = is_active)),
    CONSTRAINT ck_movimientos_caja_medio_valido CHECK (((medio)::text = ANY ((ARRAY['efectivo'::character varying, 'mercadopago'::character varying])::text[]))),
    CONSTRAINT ck_movimientos_caja_monto_positivo CHECK ((monto > (0)::numeric)),
    CONSTRAINT ck_movimientos_caja_tipo_valido CHECK (((tipo)::text = ANY ((ARRAY['ingreso'::character varying, 'gasto'::character varying, 'deuda'::character varying])::text[])))
);


--
-- Name: obras_sociales; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.obras_sociales (
    id uuid NOT NULL,
    consultorio_id uuid NOT NULL,
    nombre character varying(120) NOT NULL,
    nomenclador_ref character varying(60),
    reglas_cobertura jsonb DEFAULT '{}'::jsonb NOT NULL,
    validacion_externa boolean DEFAULT false NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_obras_sociales_baja_logica_coherente CHECK (((deleted_at IS NULL) = is_active)),
    CONSTRAINT ck_obras_sociales_nombre_no_vacio CHECK ((btrim((nombre)::text) <> ''::text)),
    CONSTRAINT ck_obras_sociales_reglas_objeto CHECK ((jsonb_typeof(reglas_cobertura) = 'object'::text)),
    CONSTRAINT ck_obras_sociales_sin_validacion_externa CHECK ((NOT validacion_externa))
);


--
-- Name: odontogramas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.odontogramas (
    id uuid NOT NULL,
    historia_id uuid NOT NULL,
    version integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_odontogramas_version_positiva CHECK ((version > 0))
);


--
-- Name: pacientes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pacientes (
    id uuid NOT NULL,
    consultorio_id uuid NOT NULL,
    nombre character varying(120) NOT NULL,
    apellido character varying(120) NOT NULL,
    dni character varying(8) NOT NULL,
    fecha_nacimiento date,
    telefono character varying(16) NOT NULL,
    email character varying(255),
    obra_social_id uuid,
    nro_afiliado character varying(40),
    notas text,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_pacientes_baja_logica_coherente CHECK (((deleted_at IS NULL) = is_active)),
    CONSTRAINT ck_pacientes_cobertura_coherente CHECK (((obra_social_id IS NOT NULL) OR (nro_afiliado IS NULL))),
    CONSTRAINT ck_pacientes_dni_formato CHECK (((dni)::text ~ '^[0-9]{7,8}$'::text)),
    CONSTRAINT ck_pacientes_telefono_formato CHECK (((telefono)::text ~ '^\+549[0-9]{10}$'::text))
);


--
-- Name: prestaciones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.prestaciones (
    id uuid NOT NULL,
    codigo character varying(20) NOT NULL,
    nombre character varying(120) NOT NULL,
    duracion_min integer NOT NULL,
    precio_base numeric(12,2) NOT NULL,
    especialidad character varying(60),
    requiere_sena boolean DEFAULT false NOT NULL,
    monto_sena numeric(12,2),
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_prestaciones_baja_logica_coherente CHECK (((deleted_at IS NULL) = is_active)),
    CONSTRAINT ck_prestaciones_duracion_positiva CHECK ((duracion_min > 0)),
    CONSTRAINT ck_prestaciones_precio_no_negativo CHECK ((precio_base >= (0)::numeric)),
    CONSTRAINT ck_prestaciones_sena_coherente CHECK (((requiere_sena AND (monto_sena IS NOT NULL) AND (monto_sena > (0)::numeric)) OR ((NOT requiere_sena) AND (monto_sena IS NULL))))
);


--
-- Name: presupuestos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.presupuestos (
    id uuid NOT NULL,
    consultorio_id uuid NOT NULL,
    paciente_id uuid NOT NULL,
    profesional_id uuid NOT NULL,
    creado_por uuid NOT NULL,
    estado character varying(20) DEFAULT 'borrador'::character varying NOT NULL,
    cobertura_estado character varying(30) DEFAULT 'calculada'::character varying NOT NULL,
    subtotal numeric(12,2) NOT NULL,
    cobertura_calculada numeric(12,2) NOT NULL,
    copago numeric(12,2) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_presupuestos_baja_logica_coherente CHECK (((deleted_at IS NULL) = is_active)),
    CONSTRAINT ck_presupuestos_cobertura_estado_valido CHECK (((cobertura_estado)::text = ANY ((ARRAY['calculada'::character varying, 'pendiente_verificacion'::character varying])::text[]))),
    CONSTRAINT ck_presupuestos_estado_valido CHECK (((estado)::text = ANY ((ARRAY['borrador'::character varying, 'aceptado'::character varying, 'rechazado'::character varying, 'en_curso'::character varying, 'finalizado'::character varying])::text[]))),
    CONSTRAINT ck_presupuestos_importes_no_negativos CHECK (((subtotal >= (0)::numeric) AND (cobertura_calculada >= (0)::numeric) AND (copago >= (0)::numeric))),
    CONSTRAINT ck_presupuestos_totales_coherentes CHECK ((subtotal = (cobertura_calculada + copago)))
);


--
-- Name: profesionales; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.profesionales (
    id uuid NOT NULL,
    consultorio_id uuid NOT NULL,
    usuario_id uuid,
    matricula character varying(40) NOT NULL,
    especialidades character varying(60)[] DEFAULT '{}'::character varying[] NOT NULL,
    duracion_base_min integer NOT NULL,
    dias_atencion integer[] NOT NULL,
    hora_desde time without time zone NOT NULL,
    hora_hasta time without time zone NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_profesionales_baja_logica_coherente CHECK (((deleted_at IS NULL) = is_active)),
    CONSTRAINT ck_profesionales_dias_en_rango CHECK ((dias_atencion <@ ARRAY[0, 1, 2, 3, 4, 5, 6])),
    CONSTRAINT ck_profesionales_dias_no_vacios CHECK ((cardinality(dias_atencion) > 0)),
    CONSTRAINT ck_profesionales_duracion_base_positiva CHECK ((duracion_base_min > 0)),
    CONSTRAINT ck_profesionales_horario_coherente CHECK ((hora_hasta > hora_desde))
);


--
-- Name: profesionales_sillones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.profesionales_sillones (
    profesional_id uuid NOT NULL,
    sillon_id uuid NOT NULL
);


--
-- Name: recordatorios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recordatorios (
    id uuid NOT NULL,
    turno_id uuid NOT NULL,
    ventana character varying(3) NOT NULL,
    programado_para timestamp with time zone NOT NULL,
    estado character varying(20) DEFAULT 'pendiente'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_recordatorios_estado_valido CHECK (((estado)::text = ANY ((ARRAY['pendiente'::character varying, 'encolado'::character varying, 'enviado'::character varying, 'fallido'::character varying, 'cancelado'::character varying])::text[]))),
    CONSTRAINT ck_recordatorios_ventana_valida CHECK (((ventana)::text = ANY ((ARRAY['48h'::character varying, '24h'::character varying])::text[])))
);


--
-- Name: registro_auditoria; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.registro_auditoria (
    id uuid NOT NULL,
    usuario_id uuid,
    accion character varying(120) NOT NULL,
    entidad character varying(60) NOT NULL,
    entidad_id character varying(64) NOT NULL,
    ip character varying(45),
    dispositivo character varying(120),
    "timestamp" timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.roles (
    id uuid NOT NULL,
    nombre character varying(40) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_roles_baja_logica_coherente CHECK (((deleted_at IS NULL) = is_active))
);


--
-- Name: secuencias_comprobantes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.secuencias_comprobantes (
    consultorio_id uuid NOT NULL,
    punto_venta integer NOT NULL,
    ultimo_interno bigint DEFAULT 0 NOT NULL,
    ultimo_fiscal bigint DEFAULT 0 NOT NULL,
    CONSTRAINT ck_secuencias_comprobantes_contadores_no_negativos CHECK (((ultimo_interno >= 0) AND (ultimo_fiscal >= 0))),
    CONSTRAINT ck_secuencias_comprobantes_punto_venta_positivo CHECK ((punto_venta > 0))
);


--
-- Name: sillones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sillones (
    id uuid NOT NULL,
    consultorio_id uuid NOT NULL,
    nombre character varying(60) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_sillones_baja_logica_coherente CHECK (((deleted_at IS NULL) = is_active))
);


--
-- Name: tokens_un_solo_uso; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tokens_un_solo_uso (
    id uuid NOT NULL,
    token_hash character varying(64) NOT NULL,
    tipo character varying(40) NOT NULL,
    entidad_tipo character varying(40) NOT NULL,
    entidad_id character varying(64) NOT NULL,
    usado boolean DEFAULT false NOT NULL,
    usado_at timestamp with time zone,
    expira_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_tokens_un_solo_uso_usado_coherente CHECK ((usado = (usado_at IS NOT NULL)))
);


--
-- Name: turnos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.turnos (
    id uuid NOT NULL,
    consultorio_id uuid NOT NULL,
    paciente_id uuid NOT NULL,
    profesional_id uuid NOT NULL,
    sillon_id uuid NOT NULL,
    prestacion_id uuid,
    inicio timestamp with time zone NOT NULL,
    fin timestamp with time zone NOT NULL,
    estado character varying(20) DEFAULT 'reservado'::character varying NOT NULL,
    origen character varying(20) DEFAULT 'recepcion'::character varying NOT NULL,
    es_sobreturno boolean DEFAULT false NOT NULL,
    color_sobreturno character varying(7),
    token_publico character varying(64),
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    sena_estado character varying(20) DEFAULT 'no_requiere'::character varying NOT NULL,
    CONSTRAINT ck_turnos_baja_logica_coherente CHECK (((deleted_at IS NULL) = is_active)),
    CONSTRAINT ck_turnos_color_sobreturno_formato CHECK (((color_sobreturno IS NULL) OR ((color_sobreturno)::text ~ '^#[0-9A-Fa-f]{6}$'::text))),
    CONSTRAINT ck_turnos_estado_valido CHECK (((estado)::text = ANY ((ARRAY['reservado'::character varying, 'confirmado'::character varying, 'en_sala'::character varying, 'atendido'::character varying, 'cancelado'::character varying, 'ausente'::character varying])::text[]))),
    CONSTRAINT ck_turnos_origen_valido CHECK (((origen)::text = ANY ((ARRAY['recepcion'::character varying, 'online'::character varying, 'whatsapp'::character varying])::text[]))),
    CONSTRAINT ck_turnos_rango_coherente CHECK ((fin > inicio)),
    CONSTRAINT ck_turnos_sena_estado_valido CHECK (((sena_estado)::text = ANY ((ARRAY['no_requiere'::character varying, 'pendiente'::character varying, 'pagada'::character varying, 'perdida'::character varying])::text[]))),
    CONSTRAINT ck_turnos_sobreturno_coherente CHECK ((es_sobreturno = (color_sobreturno IS NOT NULL)))
);


--
-- Name: usuario_roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuario_roles (
    usuario_id uuid NOT NULL,
    rol_id uuid NOT NULL
);


--
-- Name: usuarios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuarios (
    id uuid NOT NULL,
    nombre character varying(120) NOT NULL,
    email character varying(255) NOT NULL,
    hash_password character varying(255) NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_usuarios_baja_logica_coherente CHECK (((deleted_at IS NULL) = is_active))
);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: liquidaciones_obras_sociales ex_liquidaciones_periodo; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.liquidaciones_obras_sociales
    ADD CONSTRAINT ex_liquidaciones_periodo EXCLUDE USING gist (obra_social_id WITH =, daterange(desde, hasta, '[]'::text) WITH &&) WHERE ((deleted_at IS NULL));


--
-- Name: entradas_lista_espera ex_lista_espera_profesional; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entradas_lista_espera
    ADD CONSTRAINT ex_lista_espera_profesional EXCLUDE USING gist (oferta_profesional_id WITH =, tstzrange(oferta_inicio, oferta_fin, '[)'::text) WITH &&) WHERE ((((estado)::text = 'ofrecido'::text) AND (deleted_at IS NULL)));


--
-- Name: entradas_lista_espera ex_lista_espera_sillon; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entradas_lista_espera
    ADD CONSTRAINT ex_lista_espera_sillon EXCLUDE USING gist (oferta_sillon_id WITH =, tstzrange(oferta_inicio, oferta_fin, '[)'::text) WITH &&) WHERE ((((estado)::text = 'ofrecido'::text) AND (deleted_at IS NULL)));


--
-- Name: turnos ex_turnos_profesional; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.turnos
    ADD CONSTRAINT ex_turnos_profesional EXCLUDE USING gist (profesional_id WITH =, tstzrange(inicio, fin, '[)'::text) WITH &&) WHERE (((deleted_at IS NULL) AND (NOT es_sobreturno) AND ((estado)::text = ANY ((ARRAY['reservado'::character varying, 'confirmado'::character varying, 'en_sala'::character varying, 'atendido'::character varying])::text[]))));


--
-- Name: turnos ex_turnos_sillon; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.turnos
    ADD CONSTRAINT ex_turnos_sillon EXCLUDE USING gist (sillon_id WITH =, tstzrange(inicio, fin, '[)'::text) WITH &&) WHERE (((deleted_at IS NULL) AND (NOT es_sobreturno) AND ((estado)::text = ANY ((ARRAY['reservado'::character varying, 'confirmado'::character varying, 'en_sala'::character varying, 'atendido'::character varying])::text[]))));


--
-- Name: adjuntos pk_adjuntos; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.adjuntos
    ADD CONSTRAINT pk_adjuntos PRIMARY KEY (id);


--
-- Name: bloqueos pk_bloqueos; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bloqueos
    ADD CONSTRAINT pk_bloqueos PRIMARY KEY (id);


--
-- Name: cajas_diarias pk_cajas_diarias; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cajas_diarias
    ADD CONSTRAINT pk_cajas_diarias PRIMARY KEY (id);


--
-- Name: cobros pk_cobros; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cobros
    ADD CONSTRAINT pk_cobros PRIMARY KEY (id);


--
-- Name: comprobantes pk_comprobantes; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comprobantes
    ADD CONSTRAINT pk_comprobantes PRIMARY KEY (id);


--
-- Name: comprobantes_envios pk_comprobantes_envios; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comprobantes_envios
    ADD CONSTRAINT pk_comprobantes_envios PRIMARY KEY (id);


--
-- Name: consentimientos pk_consentimientos; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consentimientos
    ADD CONSTRAINT pk_consentimientos PRIMARY KEY (id);


--
-- Name: consultorios pk_consultorios; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consultorios
    ADD CONSTRAINT pk_consultorios PRIMARY KEY (id);


--
-- Name: entradas_lista_espera pk_entradas_lista_espera; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entradas_lista_espera
    ADD CONSTRAINT pk_entradas_lista_espera PRIMARY KEY (id);


--
-- Name: evoluciones pk_evoluciones; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evoluciones
    ADD CONSTRAINT pk_evoluciones PRIMARY KEY (id);


--
-- Name: exportaciones pk_exportaciones; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exportaciones
    ADD CONSTRAINT pk_exportaciones PRIMARY KEY (id);


--
-- Name: hallazgos_dentales pk_hallazgos_dentales; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hallazgos_dentales
    ADD CONSTRAINT pk_hallazgos_dentales PRIMARY KEY (id);


--
-- Name: historias_clinicas pk_historias_clinicas; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.historias_clinicas
    ADD CONSTRAINT pk_historias_clinicas PRIMARY KEY (id);


--
-- Name: items_liquidacion pk_items_liquidacion; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.items_liquidacion
    ADD CONSTRAINT pk_items_liquidacion PRIMARY KEY (id);


--
-- Name: items_presupuesto pk_items_presupuesto; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.items_presupuesto
    ADD CONSTRAINT pk_items_presupuesto PRIMARY KEY (id);


--
-- Name: liquidaciones_obras_sociales pk_liquidaciones_obras_sociales; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.liquidaciones_obras_sociales
    ADD CONSTRAINT pk_liquidaciones_obras_sociales PRIMARY KEY (id);


--
-- Name: mensajes_whatsapp pk_mensajes_whatsapp; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mensajes_whatsapp
    ADD CONSTRAINT pk_mensajes_whatsapp PRIMARY KEY (id);


--
-- Name: movimientos_caja pk_movimientos_caja; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimientos_caja
    ADD CONSTRAINT pk_movimientos_caja PRIMARY KEY (id);


--
-- Name: obras_sociales pk_obras_sociales; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.obras_sociales
    ADD CONSTRAINT pk_obras_sociales PRIMARY KEY (id);


--
-- Name: odontogramas pk_odontogramas; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.odontogramas
    ADD CONSTRAINT pk_odontogramas PRIMARY KEY (id);


--
-- Name: pacientes pk_pacientes; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pacientes
    ADD CONSTRAINT pk_pacientes PRIMARY KEY (id);


--
-- Name: prestaciones pk_prestaciones; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prestaciones
    ADD CONSTRAINT pk_prestaciones PRIMARY KEY (id);


--
-- Name: presupuestos pk_presupuestos; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.presupuestos
    ADD CONSTRAINT pk_presupuestos PRIMARY KEY (id);


--
-- Name: profesionales pk_profesionales; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profesionales
    ADD CONSTRAINT pk_profesionales PRIMARY KEY (id);


--
-- Name: profesionales_sillones pk_profesionales_sillones; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profesionales_sillones
    ADD CONSTRAINT pk_profesionales_sillones PRIMARY KEY (profesional_id, sillon_id);


--
-- Name: recordatorios pk_recordatorios; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recordatorios
    ADD CONSTRAINT pk_recordatorios PRIMARY KEY (id);


--
-- Name: registro_auditoria pk_registro_auditoria; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registro_auditoria
    ADD CONSTRAINT pk_registro_auditoria PRIMARY KEY (id);


--
-- Name: roles pk_roles; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT pk_roles PRIMARY KEY (id);


--
-- Name: secuencias_comprobantes pk_secuencias_comprobantes; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.secuencias_comprobantes
    ADD CONSTRAINT pk_secuencias_comprobantes PRIMARY KEY (consultorio_id, punto_venta);


--
-- Name: sillones pk_sillones; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sillones
    ADD CONSTRAINT pk_sillones PRIMARY KEY (id);


--
-- Name: tokens_un_solo_uso pk_tokens_un_solo_uso; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tokens_un_solo_uso
    ADD CONSTRAINT pk_tokens_un_solo_uso PRIMARY KEY (id);


--
-- Name: turnos pk_turnos; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.turnos
    ADD CONSTRAINT pk_turnos PRIMARY KEY (id);


--
-- Name: usuario_roles pk_usuario_roles; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_roles
    ADD CONSTRAINT pk_usuario_roles PRIMARY KEY (usuario_id, rol_id);


--
-- Name: usuarios pk_usuarios; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT pk_usuarios PRIMARY KEY (id);


--
-- Name: cajas_diarias uq_cajas_diarias_consultorio_fecha; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cajas_diarias
    ADD CONSTRAINT uq_cajas_diarias_consultorio_fecha UNIQUE (consultorio_id, fecha);


--
-- Name: entradas_lista_espera uq_entradas_lista_espera_orden; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entradas_lista_espera
    ADD CONSTRAINT uq_entradas_lista_espera_orden UNIQUE (orden);


--
-- Name: hallazgos_dentales uq_hallazgos_dentales_odontograma_pieza_cara; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hallazgos_dentales
    ADD CONSTRAINT uq_hallazgos_dentales_odontograma_pieza_cara UNIQUE (odontograma_id, pieza, cara);


--
-- Name: odontogramas uq_odontogramas_historia_version; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.odontogramas
    ADD CONSTRAINT uq_odontogramas_historia_version UNIQUE (historia_id, version);


--
-- Name: ix_adjuntos_historia; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_adjuntos_historia ON public.adjuntos USING btree (historia_id, created_at);


--
-- Name: ix_bloqueos_profesional_desde; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bloqueos_profesional_desde ON public.bloqueos USING btree (profesional_id, desde);


--
-- Name: ix_bloqueos_sillon_desde; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bloqueos_sillon_desde ON public.bloqueos USING btree (sillon_id, desde);


--
-- Name: ix_cobros_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cobros_estado ON public.cobros USING btree (consultorio_id, estado);


--
-- Name: ix_cobros_paciente_fecha; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cobros_paciente_fecha ON public.cobros USING btree (consultorio_id, paciente_id, fecha_operacion);


--
-- Name: ix_cobros_presupuesto; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cobros_presupuesto ON public.cobros USING btree (presupuesto_id);


--
-- Name: ix_cobros_turno; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cobros_turno ON public.cobros USING btree (turno_id);


--
-- Name: ix_comprobantes_envios_comprobante; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_comprobantes_envios_comprobante ON public.comprobantes_envios USING btree (comprobante_id);


--
-- Name: ix_comprobantes_estado_proximo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_comprobantes_estado_proximo ON public.comprobantes USING btree (estado, proximo_intento);


--
-- Name: ix_comprobantes_fecha; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_comprobantes_fecha ON public.comprobantes USING btree (consultorio_id, fecha_emision);


--
-- Name: ix_comprobantes_paciente; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_comprobantes_paciente ON public.comprobantes USING btree (paciente_id);


--
-- Name: ix_consentimientos_paciente_fecha; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_consentimientos_paciente_fecha ON public.consentimientos USING btree (consultorio_id, paciente_id, fecha);


--
-- Name: ix_entradas_lista_espera_cola; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_entradas_lista_espera_cola ON public.entradas_lista_espera USING btree (consultorio_id, estado, orden);


--
-- Name: ix_entradas_lista_espera_prestacion; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_entradas_lista_espera_prestacion ON public.entradas_lista_espera USING btree (prestacion_id, estado, orden);


--
-- Name: ix_entradas_lista_espera_retencion_profesional; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_entradas_lista_espera_retencion_profesional ON public.entradas_lista_espera USING btree (oferta_profesional_id, oferta_inicio);


--
-- Name: ix_entradas_lista_espera_retencion_sillon; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_entradas_lista_espera_retencion_sillon ON public.entradas_lista_espera USING btree (oferta_sillon_id, oferta_inicio);


--
-- Name: ix_entradas_lista_espera_vencimiento; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_entradas_lista_espera_vencimiento ON public.entradas_lista_espera USING btree (estado, oferta_expira_en);


--
-- Name: ix_evoluciones_historia_fecha; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evoluciones_historia_fecha ON public.evoluciones USING btree (historia_id, fecha);


--
-- Name: ix_exportaciones_consultorio_fecha; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_exportaciones_consultorio_fecha ON public.exportaciones USING btree (consultorio_id, created_at);


--
-- Name: ix_exportaciones_estado_proximo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_exportaciones_estado_proximo ON public.exportaciones USING btree (estado, proximo_intento);


--
-- Name: ix_exportaciones_paciente; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_exportaciones_paciente ON public.exportaciones USING btree (paciente_id);


--
-- Name: ix_items_liquidacion_cobro; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_items_liquidacion_cobro ON public.items_liquidacion USING btree (cobro_id);


--
-- Name: ix_items_liquidacion_liquidacion; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_items_liquidacion_liquidacion ON public.items_liquidacion USING btree (liquidacion_id);


--
-- Name: ix_items_liquidacion_presupuesto; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_items_liquidacion_presupuesto ON public.items_liquidacion USING btree (presupuesto_id);


--
-- Name: ix_items_presupuesto_presupuesto; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_items_presupuesto_presupuesto ON public.items_presupuesto USING btree (presupuesto_id);


--
-- Name: ix_liquidaciones_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_liquidaciones_estado ON public.liquidaciones_obras_sociales USING btree (estado);


--
-- Name: ix_liquidaciones_obras_social_periodo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_liquidaciones_obras_social_periodo ON public.liquidaciones_obras_sociales USING btree (consultorio_id, obra_social_id, desde);


--
-- Name: ix_mensajes_whatsapp_estado_proximo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mensajes_whatsapp_estado_proximo ON public.mensajes_whatsapp USING btree (estado_envio, proximo_intento);


--
-- Name: ix_mensajes_whatsapp_lista_espera; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mensajes_whatsapp_lista_espera ON public.mensajes_whatsapp USING btree (lista_espera_id);


--
-- Name: ix_mensajes_whatsapp_turno; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mensajes_whatsapp_turno ON public.mensajes_whatsapp USING btree (turno_id);


--
-- Name: ix_movimientos_caja_caja; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_movimientos_caja_caja ON public.movimientos_caja USING btree (caja_id);


--
-- Name: ix_pacientes_apellido_lower; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pacientes_apellido_lower ON public.pacientes USING btree (lower((apellido)::text) text_pattern_ops);


--
-- Name: ix_pacientes_telefono; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pacientes_telefono ON public.pacientes USING btree (consultorio_id, telefono);


--
-- Name: ix_presupuestos_paciente_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_presupuestos_paciente_created ON public.presupuestos USING btree (consultorio_id, paciente_id, created_at);


--
-- Name: ix_presupuestos_profesional_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_presupuestos_profesional_estado ON public.presupuestos USING btree (profesional_id, estado);


--
-- Name: ix_profesionales_consultorio; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_profesionales_consultorio ON public.profesionales USING btree (consultorio_id);


--
-- Name: ix_recordatorios_estado_programado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recordatorios_estado_programado ON public.recordatorios USING btree (estado, programado_para);


--
-- Name: ix_registro_auditoria_entidad; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_registro_auditoria_entidad ON public.registro_auditoria USING btree (entidad, entidad_id);


--
-- Name: ix_registro_auditoria_usuario_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_registro_auditoria_usuario_timestamp ON public.registro_auditoria USING btree (usuario_id, "timestamp");


--
-- Name: ix_tokens_un_solo_uso_entidad; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tokens_un_solo_uso_entidad ON public.tokens_un_solo_uso USING btree (tipo, entidad_tipo, entidad_id);


--
-- Name: ix_turnos_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_turnos_estado ON public.turnos USING btree (estado);


--
-- Name: ix_turnos_profesional_inicio; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_turnos_profesional_inicio ON public.turnos USING btree (profesional_id, inicio);


--
-- Name: ix_turnos_sillon_inicio; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_turnos_sillon_inicio ON public.turnos USING btree (sillon_id, inicio);


--
-- Name: uq_cobros_proveedor_pago; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_cobros_proveedor_pago ON public.cobros USING btree (proveedor_pago_id) WHERE (proveedor_pago_id IS NOT NULL);


--
-- Name: uq_cobros_sena_turno; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_cobros_sena_turno ON public.cobros USING btree (turno_id) WHERE (((tipo)::text = 'sena'::text) AND ((estado)::text = ANY ((ARRAY['pendiente'::character varying, 'aprobado'::character varying, 'perdido'::character varying])::text[])));


--
-- Name: uq_comprobantes_cae; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_comprobantes_cae ON public.comprobantes USING btree (ambiente, cae) WHERE (cae IS NOT NULL);


--
-- Name: uq_comprobantes_cobro; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_comprobantes_cobro ON public.comprobantes USING btree (cobro_id);


--
-- Name: uq_comprobantes_envios_comprobante_canal; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_comprobantes_envios_comprobante_canal ON public.comprobantes_envios USING btree (comprobante_id, canal);


--
-- Name: uq_comprobantes_fiscal; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_comprobantes_fiscal ON public.comprobantes USING btree (ambiente, punto_venta, numero_fiscal) WHERE (numero_fiscal IS NOT NULL);


--
-- Name: uq_comprobantes_numero_interno; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_comprobantes_numero_interno ON public.comprobantes USING btree (consultorio_id, punto_venta, numero_interno);


--
-- Name: uq_consultorios_slug_activo; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_consultorios_slug_activo ON public.consultorios USING btree (slug) WHERE (deleted_at IS NULL);


--
-- Name: uq_entradas_lista_espera_pendiente; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_entradas_lista_espera_pendiente ON public.entradas_lista_espera USING btree (paciente_id, prestacion_id, COALESCE(profesional_id, '00000000-0000-0000-0000-000000000000'::uuid)) WHERE (((estado)::text = 'pendiente'::text) AND (deleted_at IS NULL));


--
-- Name: uq_entradas_lista_espera_turno; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_entradas_lista_espera_turno ON public.entradas_lista_espera USING btree (turno_id) WHERE (turno_id IS NOT NULL);


--
-- Name: uq_evoluciones_rectificacion_activa; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_evoluciones_rectificacion_activa ON public.evoluciones USING btree (rectifica_a) WHERE ((rectifica_a IS NOT NULL) AND (deleted_at IS NULL));


--
-- Name: uq_exportaciones_en_curso; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_exportaciones_en_curso ON public.exportaciones USING btree (consultorio_id, solicitado_por, alcance, COALESCE(paciente_id, '00000000-0000-0000-0000-000000000000'::uuid)) WHERE ((estado)::text = ANY ((ARRAY['pendiente'::character varying, 'generando'::character varying])::text[]));


--
-- Name: uq_historias_clinicas_paciente_activa; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_historias_clinicas_paciente_activa ON public.historias_clinicas USING btree (paciente_id) WHERE (deleted_at IS NULL);


--
-- Name: uq_items_liquidacion_item; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_items_liquidacion_item ON public.items_liquidacion USING btree (item_presupuesto_id) WHERE (deleted_at IS NULL);


--
-- Name: uq_mensajes_whatsapp_proveedor; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_mensajes_whatsapp_proveedor ON public.mensajes_whatsapp USING btree (proveedor_mensaje_id) WHERE (proveedor_mensaje_id IS NOT NULL);


--
-- Name: uq_movimientos_caja_cobro; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_movimientos_caja_cobro ON public.movimientos_caja USING btree (cobro_id) WHERE (cobro_id IS NOT NULL);


--
-- Name: uq_obras_sociales_nombre_activo; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_obras_sociales_nombre_activo ON public.obras_sociales USING btree (consultorio_id, lower((nombre)::text)) WHERE (deleted_at IS NULL);


--
-- Name: uq_pacientes_dni_activo; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_pacientes_dni_activo ON public.pacientes USING btree (consultorio_id, dni) WHERE (deleted_at IS NULL);


--
-- Name: uq_prestaciones_codigo_activo; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_prestaciones_codigo_activo ON public.prestaciones USING btree (codigo) WHERE (deleted_at IS NULL);


--
-- Name: uq_profesionales_matricula_activo; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_profesionales_matricula_activo ON public.profesionales USING btree (consultorio_id, matricula) WHERE (deleted_at IS NULL);


--
-- Name: uq_profesionales_usuario_activo; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_profesionales_usuario_activo ON public.profesionales USING btree (usuario_id) WHERE ((usuario_id IS NOT NULL) AND (deleted_at IS NULL));


--
-- Name: uq_recordatorios_turno_ventana; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_recordatorios_turno_ventana ON public.recordatorios USING btree (turno_id, ventana);


--
-- Name: uq_roles_nombre_activo; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_roles_nombre_activo ON public.roles USING btree (nombre) WHERE (deleted_at IS NULL);


--
-- Name: uq_sillones_nombre_activo; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_sillones_nombre_activo ON public.sillones USING btree (consultorio_id, nombre) WHERE (deleted_at IS NULL);


--
-- Name: uq_tokens_un_solo_uso_token_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_tokens_un_solo_uso_token_hash ON public.tokens_un_solo_uso USING btree (token_hash);


--
-- Name: uq_turnos_token_publico; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_turnos_token_publico ON public.turnos USING btree (token_publico) WHERE (token_publico IS NOT NULL);


--
-- Name: uq_usuarios_email_activo; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_usuarios_email_activo ON public.usuarios USING btree (email) WHERE (deleted_at IS NULL);


--
-- Name: consentimientos trg_consentimientos_append_only; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_consentimientos_append_only BEFORE DELETE OR UPDATE ON public.consentimientos FOR EACH ROW EXECUTE FUNCTION public.consentimientos_append_only();


--
-- Name: evoluciones trg_evoluciones_inmutabilidad; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_evoluciones_inmutabilidad BEFORE DELETE OR UPDATE ON public.evoluciones FOR EACH ROW EXECUTE FUNCTION public.evoluciones_inmutabilidad();


--
-- Name: hallazgos_dentales trg_hallazgos_dentales_append_only; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_hallazgos_dentales_append_only BEFORE DELETE OR UPDATE ON public.hallazgos_dentales FOR EACH ROW EXECUTE FUNCTION public.hallazgos_dentales_append_only();


--
-- Name: odontogramas trg_odontogramas_append_only; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_odontogramas_append_only BEFORE DELETE OR UPDATE ON public.odontogramas FOR EACH ROW EXECUTE FUNCTION public.odontogramas_append_only();


--
-- Name: registro_auditoria trg_registro_auditoria_sin_truncate; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_registro_auditoria_sin_truncate BEFORE TRUNCATE ON public.registro_auditoria FOR EACH STATEMENT EXECUTE FUNCTION public.registro_auditoria_append_only();


--
-- Name: registro_auditoria trg_registro_auditoria_sin_update_delete; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_registro_auditoria_sin_update_delete BEFORE DELETE OR UPDATE ON public.registro_auditoria FOR EACH ROW EXECUTE FUNCTION public.registro_auditoria_append_only();


--
-- Name: adjuntos fk_adjuntos_historia_id_historias_clinicas; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.adjuntos
    ADD CONSTRAINT fk_adjuntos_historia_id_historias_clinicas FOREIGN KEY (historia_id) REFERENCES public.historias_clinicas(id) ON DELETE RESTRICT;


--
-- Name: adjuntos fk_adjuntos_subido_por_usuarios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.adjuntos
    ADD CONSTRAINT fk_adjuntos_subido_por_usuarios FOREIGN KEY (subido_por) REFERENCES public.usuarios(id) ON DELETE RESTRICT;


--
-- Name: bloqueos fk_bloqueos_profesional_id_profesionales; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bloqueos
    ADD CONSTRAINT fk_bloqueos_profesional_id_profesionales FOREIGN KEY (profesional_id) REFERENCES public.profesionales(id) ON DELETE RESTRICT;


--
-- Name: bloqueos fk_bloqueos_sillon_id_sillones; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bloqueos
    ADD CONSTRAINT fk_bloqueos_sillon_id_sillones FOREIGN KEY (sillon_id) REFERENCES public.sillones(id) ON DELETE RESTRICT;


--
-- Name: cajas_diarias fk_cajas_diarias_cerrada_por_usuarios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cajas_diarias
    ADD CONSTRAINT fk_cajas_diarias_cerrada_por_usuarios FOREIGN KEY (cerrada_por) REFERENCES public.usuarios(id) ON DELETE RESTRICT;


--
-- Name: cajas_diarias fk_cajas_diarias_consultorio_id_consultorios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cajas_diarias
    ADD CONSTRAINT fk_cajas_diarias_consultorio_id_consultorios FOREIGN KEY (consultorio_id) REFERENCES public.consultorios(id) ON DELETE RESTRICT;


--
-- Name: cobros fk_cobros_consultorio_id_consultorios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cobros
    ADD CONSTRAINT fk_cobros_consultorio_id_consultorios FOREIGN KEY (consultorio_id) REFERENCES public.consultorios(id) ON DELETE RESTRICT;


--
-- Name: cobros fk_cobros_creado_por_usuarios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cobros
    ADD CONSTRAINT fk_cobros_creado_por_usuarios FOREIGN KEY (creado_por) REFERENCES public.usuarios(id) ON DELETE RESTRICT;


--
-- Name: cobros fk_cobros_paciente_id_pacientes; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cobros
    ADD CONSTRAINT fk_cobros_paciente_id_pacientes FOREIGN KEY (paciente_id) REFERENCES public.pacientes(id) ON DELETE RESTRICT;


--
-- Name: cobros fk_cobros_presupuesto_id_presupuestos; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cobros
    ADD CONSTRAINT fk_cobros_presupuesto_id_presupuestos FOREIGN KEY (presupuesto_id) REFERENCES public.presupuestos(id) ON DELETE RESTRICT;


--
-- Name: cobros fk_cobros_turno_id_turnos; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cobros
    ADD CONSTRAINT fk_cobros_turno_id_turnos FOREIGN KEY (turno_id) REFERENCES public.turnos(id) ON DELETE RESTRICT;


--
-- Name: comprobantes fk_comprobantes_cobro_id_cobros; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comprobantes
    ADD CONSTRAINT fk_comprobantes_cobro_id_cobros FOREIGN KEY (cobro_id) REFERENCES public.cobros(id) ON DELETE RESTRICT;


--
-- Name: comprobantes fk_comprobantes_consultorio_id_consultorios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comprobantes
    ADD CONSTRAINT fk_comprobantes_consultorio_id_consultorios FOREIGN KEY (consultorio_id) REFERENCES public.consultorios(id) ON DELETE RESTRICT;


--
-- Name: comprobantes_envios fk_comprobantes_envios_comprobante_id_comprobantes; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comprobantes_envios
    ADD CONSTRAINT fk_comprobantes_envios_comprobante_id_comprobantes FOREIGN KEY (comprobante_id) REFERENCES public.comprobantes(id) ON DELETE RESTRICT;


--
-- Name: comprobantes_envios fk_comprobantes_envios_creado_por_usuarios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comprobantes_envios
    ADD CONSTRAINT fk_comprobantes_envios_creado_por_usuarios FOREIGN KEY (creado_por) REFERENCES public.usuarios(id) ON DELETE RESTRICT;


--
-- Name: comprobantes fk_comprobantes_paciente_id_pacientes; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comprobantes
    ADD CONSTRAINT fk_comprobantes_paciente_id_pacientes FOREIGN KEY (paciente_id) REFERENCES public.pacientes(id) ON DELETE RESTRICT;


--
-- Name: consentimientos fk_consentimientos_consultorio_id_consultorios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consentimientos
    ADD CONSTRAINT fk_consentimientos_consultorio_id_consultorios FOREIGN KEY (consultorio_id) REFERENCES public.consultorios(id) ON DELETE RESTRICT;


--
-- Name: consentimientos fk_consentimientos_paciente_id_pacientes; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consentimientos
    ADD CONSTRAINT fk_consentimientos_paciente_id_pacientes FOREIGN KEY (paciente_id) REFERENCES public.pacientes(id) ON DELETE RESTRICT;


--
-- Name: consentimientos fk_consentimientos_registrado_por_usuarios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.consentimientos
    ADD CONSTRAINT fk_consentimientos_registrado_por_usuarios FOREIGN KEY (registrado_por) REFERENCES public.usuarios(id) ON DELETE RESTRICT;


--
-- Name: entradas_lista_espera fk_entradas_lista_espera_consultorio_id_consultorios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entradas_lista_espera
    ADD CONSTRAINT fk_entradas_lista_espera_consultorio_id_consultorios FOREIGN KEY (consultorio_id) REFERENCES public.consultorios(id) ON DELETE RESTRICT;


--
-- Name: entradas_lista_espera fk_entradas_lista_espera_oferta_profesional_id_profesionales; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entradas_lista_espera
    ADD CONSTRAINT fk_entradas_lista_espera_oferta_profesional_id_profesionales FOREIGN KEY (oferta_profesional_id) REFERENCES public.profesionales(id) ON DELETE RESTRICT;


--
-- Name: entradas_lista_espera fk_entradas_lista_espera_oferta_sillon_id_sillones; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entradas_lista_espera
    ADD CONSTRAINT fk_entradas_lista_espera_oferta_sillon_id_sillones FOREIGN KEY (oferta_sillon_id) REFERENCES public.sillones(id) ON DELETE RESTRICT;


--
-- Name: entradas_lista_espera fk_entradas_lista_espera_paciente_id_pacientes; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entradas_lista_espera
    ADD CONSTRAINT fk_entradas_lista_espera_paciente_id_pacientes FOREIGN KEY (paciente_id) REFERENCES public.pacientes(id) ON DELETE RESTRICT;


--
-- Name: entradas_lista_espera fk_entradas_lista_espera_prestacion_id_prestaciones; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entradas_lista_espera
    ADD CONSTRAINT fk_entradas_lista_espera_prestacion_id_prestaciones FOREIGN KEY (prestacion_id) REFERENCES public.prestaciones(id) ON DELETE RESTRICT;


--
-- Name: entradas_lista_espera fk_entradas_lista_espera_profesional_id_profesionales; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entradas_lista_espera
    ADD CONSTRAINT fk_entradas_lista_espera_profesional_id_profesionales FOREIGN KEY (profesional_id) REFERENCES public.profesionales(id) ON DELETE RESTRICT;


--
-- Name: entradas_lista_espera fk_entradas_lista_espera_turno_id_turnos; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entradas_lista_espera
    ADD CONSTRAINT fk_entradas_lista_espera_turno_id_turnos FOREIGN KEY (turno_id) REFERENCES public.turnos(id) ON DELETE RESTRICT;


--
-- Name: evoluciones fk_evoluciones_creado_por_usuarios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evoluciones
    ADD CONSTRAINT fk_evoluciones_creado_por_usuarios FOREIGN KEY (creado_por) REFERENCES public.usuarios(id) ON DELETE RESTRICT;


--
-- Name: evoluciones fk_evoluciones_firmada_por_usuarios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evoluciones
    ADD CONSTRAINT fk_evoluciones_firmada_por_usuarios FOREIGN KEY (firmada_por) REFERENCES public.usuarios(id) ON DELETE RESTRICT;


--
-- Name: evoluciones fk_evoluciones_historia_id_historias_clinicas; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evoluciones
    ADD CONSTRAINT fk_evoluciones_historia_id_historias_clinicas FOREIGN KEY (historia_id) REFERENCES public.historias_clinicas(id) ON DELETE RESTRICT;


--
-- Name: evoluciones fk_evoluciones_profesional_id_profesionales; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evoluciones
    ADD CONSTRAINT fk_evoluciones_profesional_id_profesionales FOREIGN KEY (profesional_id) REFERENCES public.profesionales(id) ON DELETE RESTRICT;


--
-- Name: evoluciones fk_evoluciones_rectifica_a_evoluciones; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evoluciones
    ADD CONSTRAINT fk_evoluciones_rectifica_a_evoluciones FOREIGN KEY (rectifica_a) REFERENCES public.evoluciones(id) ON DELETE RESTRICT;


--
-- Name: exportaciones fk_exportaciones_consultorio_id_consultorios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exportaciones
    ADD CONSTRAINT fk_exportaciones_consultorio_id_consultorios FOREIGN KEY (consultorio_id) REFERENCES public.consultorios(id) ON DELETE RESTRICT;


--
-- Name: exportaciones fk_exportaciones_paciente_id_pacientes; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exportaciones
    ADD CONSTRAINT fk_exportaciones_paciente_id_pacientes FOREIGN KEY (paciente_id) REFERENCES public.pacientes(id) ON DELETE RESTRICT;


--
-- Name: exportaciones fk_exportaciones_solicitado_por_usuarios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.exportaciones
    ADD CONSTRAINT fk_exportaciones_solicitado_por_usuarios FOREIGN KEY (solicitado_por) REFERENCES public.usuarios(id) ON DELETE RESTRICT;


--
-- Name: hallazgos_dentales fk_hallazgos_dentales_odontograma_id_odontogramas; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hallazgos_dentales
    ADD CONSTRAINT fk_hallazgos_dentales_odontograma_id_odontogramas FOREIGN KEY (odontograma_id) REFERENCES public.odontogramas(id) ON DELETE RESTRICT;


--
-- Name: historias_clinicas fk_historias_clinicas_abierta_por_usuarios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.historias_clinicas
    ADD CONSTRAINT fk_historias_clinicas_abierta_por_usuarios FOREIGN KEY (abierta_por) REFERENCES public.usuarios(id) ON DELETE RESTRICT;


--
-- Name: historias_clinicas fk_historias_clinicas_consultorio_id_consultorios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.historias_clinicas
    ADD CONSTRAINT fk_historias_clinicas_consultorio_id_consultorios FOREIGN KEY (consultorio_id) REFERENCES public.consultorios(id) ON DELETE RESTRICT;


--
-- Name: historias_clinicas fk_historias_clinicas_paciente_id_pacientes; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.historias_clinicas
    ADD CONSTRAINT fk_historias_clinicas_paciente_id_pacientes FOREIGN KEY (paciente_id) REFERENCES public.pacientes(id) ON DELETE RESTRICT;


--
-- Name: items_liquidacion fk_items_liquidacion_cobro_id_cobros; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.items_liquidacion
    ADD CONSTRAINT fk_items_liquidacion_cobro_id_cobros FOREIGN KEY (cobro_id) REFERENCES public.cobros(id) ON DELETE RESTRICT;


--
-- Name: items_liquidacion fk_items_liquidacion_item_presupuesto_id_items_presupuesto; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.items_liquidacion
    ADD CONSTRAINT fk_items_liquidacion_item_presupuesto_id_items_presupuesto FOREIGN KEY (item_presupuesto_id) REFERENCES public.items_presupuesto(id) ON DELETE RESTRICT;


--
-- Name: items_liquidacion fk_items_liquidacion_liquidacion_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.items_liquidacion
    ADD CONSTRAINT fk_items_liquidacion_liquidacion_id FOREIGN KEY (liquidacion_id) REFERENCES public.liquidaciones_obras_sociales(id) ON DELETE RESTRICT;


--
-- Name: items_liquidacion fk_items_liquidacion_prestacion_id_prestaciones; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.items_liquidacion
    ADD CONSTRAINT fk_items_liquidacion_prestacion_id_prestaciones FOREIGN KEY (prestacion_id) REFERENCES public.prestaciones(id) ON DELETE RESTRICT;


--
-- Name: items_liquidacion fk_items_liquidacion_presupuesto_id_presupuestos; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.items_liquidacion
    ADD CONSTRAINT fk_items_liquidacion_presupuesto_id_presupuestos FOREIGN KEY (presupuesto_id) REFERENCES public.presupuestos(id) ON DELETE RESTRICT;


--
-- Name: items_presupuesto fk_items_presupuesto_prestacion_id_prestaciones; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.items_presupuesto
    ADD CONSTRAINT fk_items_presupuesto_prestacion_id_prestaciones FOREIGN KEY (prestacion_id) REFERENCES public.prestaciones(id) ON DELETE RESTRICT;


--
-- Name: items_presupuesto fk_items_presupuesto_presupuesto_id_presupuestos; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.items_presupuesto
    ADD CONSTRAINT fk_items_presupuesto_presupuesto_id_presupuestos FOREIGN KEY (presupuesto_id) REFERENCES public.presupuestos(id) ON DELETE RESTRICT;


--
-- Name: liquidaciones_obras_sociales fk_liquidaciones_obras_sociales_cerrada_por_usuarios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.liquidaciones_obras_sociales
    ADD CONSTRAINT fk_liquidaciones_obras_sociales_cerrada_por_usuarios FOREIGN KEY (cerrada_por) REFERENCES public.usuarios(id) ON DELETE RESTRICT;


--
-- Name: liquidaciones_obras_sociales fk_liquidaciones_obras_sociales_consultorio_id_consultorios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.liquidaciones_obras_sociales
    ADD CONSTRAINT fk_liquidaciones_obras_sociales_consultorio_id_consultorios FOREIGN KEY (consultorio_id) REFERENCES public.consultorios(id) ON DELETE RESTRICT;


--
-- Name: liquidaciones_obras_sociales fk_liquidaciones_obras_sociales_creado_por_usuarios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.liquidaciones_obras_sociales
    ADD CONSTRAINT fk_liquidaciones_obras_sociales_creado_por_usuarios FOREIGN KEY (creado_por) REFERENCES public.usuarios(id) ON DELETE RESTRICT;


--
-- Name: liquidaciones_obras_sociales fk_liquidaciones_obras_sociales_obra_social_id_obras_sociales; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.liquidaciones_obras_sociales
    ADD CONSTRAINT fk_liquidaciones_obras_sociales_obra_social_id_obras_sociales FOREIGN KEY (obra_social_id) REFERENCES public.obras_sociales(id) ON DELETE RESTRICT;


--
-- Name: mensajes_whatsapp fk_mensajes_whatsapp_lista_espera_id_entradas_lista_espera; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mensajes_whatsapp
    ADD CONSTRAINT fk_mensajes_whatsapp_lista_espera_id_entradas_lista_espera FOREIGN KEY (lista_espera_id) REFERENCES public.entradas_lista_espera(id) ON DELETE RESTRICT;


--
-- Name: mensajes_whatsapp fk_mensajes_whatsapp_recordatorio_id_recordatorios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mensajes_whatsapp
    ADD CONSTRAINT fk_mensajes_whatsapp_recordatorio_id_recordatorios FOREIGN KEY (recordatorio_id) REFERENCES public.recordatorios(id) ON DELETE RESTRICT;


--
-- Name: mensajes_whatsapp fk_mensajes_whatsapp_turno_id_turnos; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mensajes_whatsapp
    ADD CONSTRAINT fk_mensajes_whatsapp_turno_id_turnos FOREIGN KEY (turno_id) REFERENCES public.turnos(id) ON DELETE RESTRICT;


--
-- Name: movimientos_caja fk_movimientos_caja_caja_id_cajas_diarias; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimientos_caja
    ADD CONSTRAINT fk_movimientos_caja_caja_id_cajas_diarias FOREIGN KEY (caja_id) REFERENCES public.cajas_diarias(id) ON DELETE RESTRICT;


--
-- Name: movimientos_caja fk_movimientos_caja_cobro_id_cobros; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimientos_caja
    ADD CONSTRAINT fk_movimientos_caja_cobro_id_cobros FOREIGN KEY (cobro_id) REFERENCES public.cobros(id) ON DELETE RESTRICT;


--
-- Name: movimientos_caja fk_movimientos_caja_creado_por_usuarios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimientos_caja
    ADD CONSTRAINT fk_movimientos_caja_creado_por_usuarios FOREIGN KEY (creado_por) REFERENCES public.usuarios(id) ON DELETE RESTRICT;


--
-- Name: obras_sociales fk_obras_sociales_consultorio_id_consultorios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.obras_sociales
    ADD CONSTRAINT fk_obras_sociales_consultorio_id_consultorios FOREIGN KEY (consultorio_id) REFERENCES public.consultorios(id) ON DELETE RESTRICT;


--
-- Name: odontogramas fk_odontogramas_historia_id_historias_clinicas; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.odontogramas
    ADD CONSTRAINT fk_odontogramas_historia_id_historias_clinicas FOREIGN KEY (historia_id) REFERENCES public.historias_clinicas(id) ON DELETE RESTRICT;


--
-- Name: pacientes fk_pacientes_consultorio_id_consultorios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pacientes
    ADD CONSTRAINT fk_pacientes_consultorio_id_consultorios FOREIGN KEY (consultorio_id) REFERENCES public.consultorios(id) ON DELETE RESTRICT;


--
-- Name: pacientes fk_pacientes_obra_social_id_obras_sociales; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pacientes
    ADD CONSTRAINT fk_pacientes_obra_social_id_obras_sociales FOREIGN KEY (obra_social_id) REFERENCES public.obras_sociales(id) ON DELETE RESTRICT;


--
-- Name: presupuestos fk_presupuestos_consultorio_id_consultorios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.presupuestos
    ADD CONSTRAINT fk_presupuestos_consultorio_id_consultorios FOREIGN KEY (consultorio_id) REFERENCES public.consultorios(id) ON DELETE RESTRICT;


--
-- Name: presupuestos fk_presupuestos_creado_por_usuarios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.presupuestos
    ADD CONSTRAINT fk_presupuestos_creado_por_usuarios FOREIGN KEY (creado_por) REFERENCES public.usuarios(id) ON DELETE RESTRICT;


--
-- Name: presupuestos fk_presupuestos_paciente_id_pacientes; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.presupuestos
    ADD CONSTRAINT fk_presupuestos_paciente_id_pacientes FOREIGN KEY (paciente_id) REFERENCES public.pacientes(id) ON DELETE RESTRICT;


--
-- Name: presupuestos fk_presupuestos_profesional_id_profesionales; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.presupuestos
    ADD CONSTRAINT fk_presupuestos_profesional_id_profesionales FOREIGN KEY (profesional_id) REFERENCES public.profesionales(id) ON DELETE RESTRICT;


--
-- Name: profesionales fk_profesionales_consultorio_id_consultorios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profesionales
    ADD CONSTRAINT fk_profesionales_consultorio_id_consultorios FOREIGN KEY (consultorio_id) REFERENCES public.consultorios(id) ON DELETE RESTRICT;


--
-- Name: profesionales_sillones fk_profesionales_sillones_profesional_id_profesionales; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profesionales_sillones
    ADD CONSTRAINT fk_profesionales_sillones_profesional_id_profesionales FOREIGN KEY (profesional_id) REFERENCES public.profesionales(id) ON DELETE RESTRICT;


--
-- Name: profesionales_sillones fk_profesionales_sillones_sillon_id_sillones; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profesionales_sillones
    ADD CONSTRAINT fk_profesionales_sillones_sillon_id_sillones FOREIGN KEY (sillon_id) REFERENCES public.sillones(id) ON DELETE RESTRICT;


--
-- Name: profesionales fk_profesionales_usuario_id_usuarios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.profesionales
    ADD CONSTRAINT fk_profesionales_usuario_id_usuarios FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id) ON DELETE RESTRICT;


--
-- Name: recordatorios fk_recordatorios_turno_id_turnos; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recordatorios
    ADD CONSTRAINT fk_recordatorios_turno_id_turnos FOREIGN KEY (turno_id) REFERENCES public.turnos(id) ON DELETE RESTRICT;


--
-- Name: registro_auditoria fk_registro_auditoria_usuario_id_usuarios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registro_auditoria
    ADD CONSTRAINT fk_registro_auditoria_usuario_id_usuarios FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id) ON DELETE RESTRICT;


--
-- Name: secuencias_comprobantes fk_secuencias_comprobantes_consultorio_id_consultorios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.secuencias_comprobantes
    ADD CONSTRAINT fk_secuencias_comprobantes_consultorio_id_consultorios FOREIGN KEY (consultorio_id) REFERENCES public.consultorios(id) ON DELETE RESTRICT;


--
-- Name: sillones fk_sillones_consultorio_id_consultorios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sillones
    ADD CONSTRAINT fk_sillones_consultorio_id_consultorios FOREIGN KEY (consultorio_id) REFERENCES public.consultorios(id) ON DELETE RESTRICT;


--
-- Name: turnos fk_turnos_consultorio_id_consultorios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.turnos
    ADD CONSTRAINT fk_turnos_consultorio_id_consultorios FOREIGN KEY (consultorio_id) REFERENCES public.consultorios(id) ON DELETE RESTRICT;


--
-- Name: turnos fk_turnos_paciente_id_pacientes; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.turnos
    ADD CONSTRAINT fk_turnos_paciente_id_pacientes FOREIGN KEY (paciente_id) REFERENCES public.pacientes(id) ON DELETE RESTRICT;


--
-- Name: turnos fk_turnos_prestacion_id_prestaciones; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.turnos
    ADD CONSTRAINT fk_turnos_prestacion_id_prestaciones FOREIGN KEY (prestacion_id) REFERENCES public.prestaciones(id) ON DELETE RESTRICT;


--
-- Name: turnos fk_turnos_profesional_id_profesionales; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.turnos
    ADD CONSTRAINT fk_turnos_profesional_id_profesionales FOREIGN KEY (profesional_id) REFERENCES public.profesionales(id) ON DELETE RESTRICT;


--
-- Name: turnos fk_turnos_sillon_id_sillones; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.turnos
    ADD CONSTRAINT fk_turnos_sillon_id_sillones FOREIGN KEY (sillon_id) REFERENCES public.sillones(id) ON DELETE RESTRICT;


--
-- Name: usuario_roles fk_usuario_roles_rol_id_roles; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_roles
    ADD CONSTRAINT fk_usuario_roles_rol_id_roles FOREIGN KEY (rol_id) REFERENCES public.roles(id) ON DELETE RESTRICT;


--
-- Name: usuario_roles fk_usuario_roles_usuario_id_usuarios; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_roles
    ADD CONSTRAINT fk_usuario_roles_usuario_id_usuarios FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id) ON DELETE RESTRICT;


--
-- PostgreSQL database dump complete
--


