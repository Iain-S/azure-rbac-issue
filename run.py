"""An Azure Function App to collect status information."""
import logging

import fire
from azure.graphrbac import GraphRbacManagementClient
from azure.graphrbac.models import GetObjectsParameters
from azure.identity import DefaultAzureCredential
from azure.mgmt.authorization import AuthorizationManagementClient as AuthClient
from azure.mgmt.subscription import SubscriptionClient
from msrestazure.azure_exceptions import CloudError

from wrapper import CredentialWrapper

CREDENTIALS = DefaultAzureCredential()

GRAPH_CREDENTIALS = CredentialWrapper(
    resource_id="https://graph.windows.net",
)


def get_all(tenant_id, sub_id):
    """Get status and role assignments."""

    logging.warning("Getting data for subscription %s.", sub_id)

    graph_client = GraphRbacManagementClient(
        credentials=GRAPH_CREDENTIALS, tenant_id=tenant_id
    )

    client = SubscriptionClient(credential=CREDENTIALS)
    subscriptions = client.subscriptions.list()

    for subscription in subscriptions:
        if subscription.subscription_id != sub_id:
            continue

        auth_client = AuthClient(
            credential=CREDENTIALS, subscription_id=sub_id
        )

        # https://docs.microsoft.com/en-us/python/api/azure-mgmt-authorization/azure.mgmt.authorization.v2015_07_01.models.roleassignmentlistresult?view=azure-python
        assignments_list = list(auth_client.role_assignments.list())

        role_defs = list(
            auth_client.role_definitions.list(
                scope="/subscriptions/" + subscription.subscription_id
            )
        )
        role_def_dict = {x.id: x.role_name for x in role_defs}

        try:
            for assignment in assignments_list:
                role_name = role_def_dict.get(assignment.properties.role_definition_id)

                params = GetObjectsParameters(
                    include_directory_object_references=True,
                    object_ids=[assignment.properties.principal_id],
                )
                results = list(graph_client.objects.get_objects_by_object_ids(params))

                mail = None
                if results:
                    display_name = results[0].display_name

                    if hasattr(results[0], "mail"):
                        mail = results[0].mail
                else:
                    logging.warning(
                        "Could not get role assignment display name",
                        str(subscription.subscription_id),
                    )
                    display_name = "unknown"

                print("role_name", role_name)
                print("display_name", display_name)
                print("mail", mail)
                print("")
            return

        except CloudError as e:
            logging.error(
                "Could not retrieve role assignments. Do you have GraphAPI permissions?"
            )
            logging.error(e)

    raise RuntimeError("Subscription not found")


def main(tenant_id, subscription_id) -> None:

    logging.basicConfig(
        level="INFO",
        format="%(asctime)s %(message)s",
        datefmt="%d/%m/%Y %I:%M:%S %p",
    )

    get_all(tenant_id, subscription_id)


if __name__ == '__main__':
    # Fire will pass on any commandline args to main()
    fire.Fire(main)
