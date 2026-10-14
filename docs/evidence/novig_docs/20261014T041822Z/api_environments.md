> ## Documentation Index
> Fetch the complete documentation index at: https://docs.novig.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Environments

> The host for each environment, and how keys work across them.

export const WEB_PROFILE = "https://novig.com/Profile/ProfileScreen";

export const HOST_VAR = "NOVIG_HOST";

export const PAPER_PROFILE = "https://paper.novig.com/Profile/ProfileScreen";

export const PAPER_APP_HOST = "https://paper.novig.com";

export const PROD_HOST = "https://api.novig.com";

export const V3_WS_HOST = "wss://api.paper.novig.com";

export const V3_HOST = "https://api.paper.novig.com";

Every example on this site reads the host from <code>{HOST_VAR}</code>. Set it once:

```bash theme={"dark"}
export NOVIG_HOST=https://api.paper.novig.com
```

| Environment | Host | Money | Location check |
| - | - | - | - |
| Paper | <code>{V3_HOST}</code> | Play | No |
| Production | <code>{PROD_HOST}</code> | Real | Yes |

Paper is our play-money exchange. It runs the same API as Production, without the location check.

In both environments, you create a key on Profile.

In Paper, use <a href={PAPER_PROFILE}>Profile</a> on paper.novig.com. In Production, use <a href={WEB_PROFILE}>Profile</a> on novig.com.

The websocket uses the same host as REST. On Paper, that's <code>{V3_WS_HOST}</code>.

## Set up a Paper account

Paper has its own web app at <a href={PAPER_APP_HOST}>{PAPER_APP_HOST}</a>. Every account starts with \$10,000 in play money, so you can trade without risk.

Paper skips the identity check. It fills in a simulated profile for you, so you never enter your real details.

<Steps>
  <Step title="Sign up">Open <a href={PAPER_APP_HOST}>paper.novig.com</a> and sign up.</Step>
  <Step title="Set up your account">Press **Fill in KYC Data, Accept all Terms, and Start with \$10,000**.</Step>
  <Step title="Create a key">Open <a href={PAPER_PROFILE}>Profile</a>, then press **Settings** and **Novig API**.</Step>
</Steps>

Production runs a real identity check and a location check, and trades real money.

## Each environment has its own keys

A key works only in the environment where you created it.
Production rejects a Paper key with `api key not found`.
Store each environment's keypair in its own secret.

## Switch environments

1. Point <code>{HOST_VAR}</code> at the new host.
2. Create a keypair in that environment.
3. Re-run the [Quickstart](/api/quickstart) to test your signature.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.