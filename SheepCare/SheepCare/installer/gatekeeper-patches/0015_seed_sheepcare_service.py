# Migracion de datos que registra SheepCare en el esquema RBAC de GateKeeper
# (ServiceMaster + PermissionMaster + ServiceRole por defecto).
#
# Este archivo NO forma parte del repositorio upstream de GateKeeper: se copia
# a gatekeeper/aegis/migrations/ por setup_gatekeeper.ps1 despues de clonar y
# fijar el commit pinneado (ver docs/gatekeeper-integration-analysis.md).
#
# El Tenant "sip11-sheepcare" ya viene sembrado por GateKeeper en la migracion
# 0012_seed_external_tenants.py; aqui solo se anade el Service y sus roles.

from django.db import migrations


def seed_sheepcare_service(apps, schema_editor):
    Tenant = apps.get_model("aegis", "Tenant")
    ServiceMaster = apps.get_model("aegis", "ServiceMaster")
    PermissionMaster = apps.get_model("aegis", "PermissionMaster")
    ServiceRole = apps.get_model("aegis", "ServiceRole")

    tenant = Tenant.objects.filter(code="sip11").first()

    service, _ = ServiceMaster.objects.update_or_create(
        service_code="sheepcare",
        defaults={
            "service_name": "SheepCare",
            "service_description": "Smart estrus detection system for sheep farms.",
        },
    )

    permissions = []
    for action in ("view", "add", "edit", "delete"):
        perm, _ = PermissionMaster.objects.update_or_create(
            service=service, action=action, defaults={"is_virtual": False},
        )
        permissions.append(perm)

    role, _ = ServiceRole.objects.update_or_create(
        tenant=tenant, service=service, role_code="operator",
        defaults={
            "role_name": "SheepCare Operator",
            "description": "Default role with full access to SheepCare.",
        },
    )
    role.permissions.set(permissions)


def unseed_sheepcare_service(apps, schema_editor):
    ServiceMaster = apps.get_model("aegis", "ServiceMaster")
    ServiceMaster.objects.filter(service_code="sheepcare").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("aegis", "0014_alter_servicerole_options_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_sheepcare_service, unseed_sheepcare_service),
    ]
