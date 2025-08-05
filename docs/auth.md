**help**

Most actions with the GPAS CLI require that the user have first authenticated with the GPAS server
with their login credentials. Upon successfully authentication, a bearer token is stored in the user's home directory
and will be used on subsequent CLI usage.

The token is valid for 7 days and a new token can be retrieved at anytime.

### Usage

Running `gpas auth` will ask for your username and password for GPAS, your password will not be shown
in the terminal session.

```bash
$ gpas auth

14:04:31 INFO: GPAS client version 2.0.0rc1
14:04:31 INFO: Authenticating with portal.eit-pathogena.com
Enter your username: gpas-user@eit.org
Enter your password:
14:04:50 INFO: Authenticated (/Users/<user>/.config/gpas/tokens/portal.eit-pathogena.com.json)
```

#### Troubleshooting Authentication

##### How do I get an account for GPAS?

Creating a Personal Account:

Navigate to GPAS and click on “Sign Up”. Follow the instructions to create a user account.

Shortly after filling out the form you'll receive a verification email. Click the link in the email to verify your
account and email address. If you don’t receive the email, please contact gpas.support@eit.org.

You are now ready to start using GPAS.

##### What happens when my token expires?

If you haven't already retrieved a token, you will receive the following error message.

```bash No token file
$ gpas upload tests/data/illumina-2.csv

12:46:42 INFO: GPAS client version 2.0.0rc1
12:46:43 INFO: Getting credit balance for portal.eit-pathogena.com
12:46:43 ERROR: FileNotFoundError: Token not found at /Users/<user>/.config/gpas/tokens/portal.eit-pathogena.com.json, have you authenticated?
```

If your token is invalid or expired, you will receive the following message

```text Invalid token
14:03:26 INFO: GPAS client version 2.0.0rc1
14:03:26 ERROR: AuthorizationError: Authorization checks failed! Please re-authenticate with `gpas auth` and
try again.
```

##### How can I check my token expiry before long running processes?

You can check the expiry of your token with the following command:

```bash
$ gpas auth --check-expiry
14:05:52 INFO: GPAS client version 2.0.0rc1
14:05:52 INFO: Current token for portal.eit-pathogena.com expires at 2024-08-13 14:04:50.672085
```
