# API Key Rotation

## Overview

API keys should be rotated periodically and immediately if a key may have been exposed.

Rotating an API key replaces the existing credential with a new credential. Applications using the old key may stop authenticating after the old key is revoked.

## When to Rotate an API Key

Rotate an API key when:

- The key has been exposed or accidentally committed to source control.
- A team member with access to the key leaves the organization.
- A security policy requires periodic credential rotation.
- Unauthorized API activity is suspected.
- The customer wants to replace an existing credential.

## API Key Rotation Procedure

1. Sign in to the administration console.
2. Open the API Keys section.
3. Select the key that needs to be rotated.
4. Create a replacement API key.
5. Update the application configuration with the new key.
6. Deploy the updated configuration.
7. Verify that API requests succeed using the new key.
8. Revoke the old API key after confirming that dependent applications are using the replacement key.

## Troubleshooting Authentication Failures

If requests fail after rotation:

- Verify that the new API key was copied correctly.
- Check that the application is using the updated environment variable.
- Restart the application if configuration values are loaded only during startup.
- Verify that the API endpoint and environment are correct.
- Check application logs for authentication errors.
- Confirm that the old key was not accidentally revoked before the new key was deployed.

## Security Guidance

Never include API keys in source code, public documentation, screenshots, tickets, or chat messages.

If an API key is suspected to be compromised, rotate it immediately and investigate recent API activity.

## Escalation

Escalate the issue to the security or support team when:

- An API key may have been publicly exposed.
- Unauthorized API activity is detected.
- Multiple applications continue failing after the key was rotated.
- The customer cannot determine which applications depend on the compromised key.

## Related Support Categories

This documentation can support:

- Integration/API issues
- Security-related incidents
- Production incidents
- Authentication failures