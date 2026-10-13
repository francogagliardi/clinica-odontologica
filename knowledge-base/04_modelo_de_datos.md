# Modelo de Datos

## Dominios

- **Agenda**: profesionales, sillones, turnos, bloqueos, sobreturnos, lista de espera.
- **Pacientes**: datos personales, contacto, cobertura.
- **Clínica**: historia clínica, evoluciones, odontograma FDI, adjuntos, consentimientos.
- **Comercial**: prestaciones, presupuestos/planes de tratamiento, obras sociales/convenios.
- **Caja**: cobros, señas, comprobantes/facturas ARCA.
- **Comunicaciones**: recordatorios, mensajes WhatsApp, tokens de enlace público.
- **Seguridad**: usuarios, roles, auditoría.

## ERD (textual)

```
Consultorio 1──* Profesional 1──* Turno *──1 Paciente
Consultorio 1──* Sillon 1──* Turno
Paciente 1──* HistoriaClinica 1──* Evolucion
HistoriaClinica 1──1 Odontograma 1──* HallazgoDental (pieza FDI + cara + estado)
Paciente 1──* Presupuesto 1──* ItemPresupuesto *──1 Prestacion
Presupuesto *──1 ObraSocial (convenio + cobertura/copago)
Paciente 1──* Cobro 1──0..1 ComprobanteARCA (CAE, QR)
Turno 1──0..1 Cobro (seña)
Turno 1──* Recordatorio 1──* MensajeWhatsApp
Turno cancelado ──→ EntradaListaEspera (orden FIFO por prestación/profesional)
Usuario *──* Rol; toda escritura clínica/admin ──→ RegistroAuditoria
Paciente 1──* Consentimiento (firma)
```

## Entidades

### Paciente
- Atributos: id, nombre, apellido, DNI, fecha_nacimiento, teléfono (WhatsApp), email, obra_social_id, nro_afiliado, notas, created_at.
- Relaciones: 1──* Turno, HistoriaClinica, Presupuesto, Cobro, Consentimiento.
- Constraints: DNI único por consultorio; teléfono requerido (canal WhatsApp).
- Índices: dni, telefono, apellido.

### Profesional
- Atributos: id, usuario_id, matrícula, especialidades[], agenda_config (duración base, horarios, días).
- Relaciones: 1──* Turno, Bloqueo; *──* Sillon (habilitaciones).

### Sillon (recurso físico / box)
- Atributos: id, nombre, consultorio_id, activo.
- Relaciones: 1──* Turno.

### Turno
- Atributos: id, paciente_id, profesional_id, sillon_id, prestacion_id, inicio, fin, estado (reservado/confirmado/en_sala/atendido/cancelado/ausente), origen (recepcion/online/whatsapp), seña_id, token_publico, created_at.
- Relaciones: *──1 Prestacion (duración variable); 1──* Recordatorio; 1──0..1 Cobro.
- Constraints: **sin solapamiento por profesional ni por sillón** (exclusión transaccional, RN-TU-01); fin = inicio + duración de la prestación salvo sobreturno marcado.
- Índices: (profesional_id, inicio), (sillon_id, inicio), estado, token_publico.

### Bloqueo
- Atributos: id, profesional_id/sillon_id, desde, hasta, motivo (licencia, feriado, administrativo).

### EntradaListaEspera
- Atributos: id, paciente_id, prestacion_id, profesional_id (opcional), orden, estado (pendiente/ofrecido/convertido/vencido), created_at.
- Regla: el hueco liberado se ofrece por orden (RN-TU-05).

### HistoriaClinica / Evolucion
- HistoriaClinica: id, paciente_id, abierta_por, fecha_apertura.
- Evolucion: id, historia_id, profesional_id, fecha, texto, created_at. Inmutable tras firma (RN-CL-04 + auditoría).

### Odontograma / HallazgoDental
- Odontograma: id, historia_id, version.
- HallazgoDental: pieza (notación FDI 11–48/51–85), cara, estado/diagnóstico (CIE-10 donde aplique), fecha.

### Prestacion
- Atributos: id, código, nombre, duración_min, precio_base, especialidad, requiere_seña (bool), monto_seña.

### Presupuesto (plan de tratamiento)
- Atributos: id, paciente_id, profesional_id, items[], cobertura_calculada, copago, estado (borrador/aceptado/rechazado/en_curso/finalizado), created_at.
- ItemPresupuesto: prestacion_id, pieza, cantidad, precio, cobertura_item.

### ObraSocial / Convenio
- Atributos: id, nombre, nomenclador_ref, reglas_cobertura, validacion_externa (bool).

### Cobro / ComprobanteARCA
- Cobro: id, paciente_id, turno_id?, presupuesto_id?, monto, medio (efectivo/MP), estado, created_at.
- ComprobanteARCA: id, cobro_id, tipo (B/C), CAE, QR, fecha_emision. Todo cobro emite comprobante (RN-AD-03).

### Recordatorio / MensajeWhatsApp
- Recordatorio: id, turno_id, programado_para (48 h / 24 h), estado.
- MensajeWhatsApp: id, recordatorio_id, plantilla, estado_envio, respuesta (confirmado/cancelado/reprogramado).

### Usuario / Rol / RegistroAuditoria
- Usuario: id, nombre, email, hash_password, activo; *──* Rol.
- RegistroAuditoria: id, usuario_id, accion, entidad, entidad_id, IP, dispositivo, timestamp. Inmutable (RN-SE-02).

### Consentimiento
- Atributos: id, paciente_id, tipo, texto_version, firma_ref, fecha.

## Seed data inicial

- Roles: administrador, odontologo, recepcionista, asistente, auditor (solo lectura).
- Usuario administrador demo + 1 odontólogo + 1 recepcionista.
- 1 consultorio demo con 2 sillones.
- Catálogo mínimo de prestaciones (consulta, limpieza, obturación, endodoncia, extracción) con duraciones y precios ficticios.
- 1 obra social ficticia de prueba ("OS Demo", convenio propio con nomenclador local — DD-11; 1 real en segunda iteración) + pacientes y turnos ficticios para la demo universitaria.
