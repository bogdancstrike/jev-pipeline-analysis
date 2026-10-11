import { Alert, Button, Typography } from "antd";

import { ApiError } from "../../api/client";

/**
 * The failure state for any data view: what failed, the server's own words, the request
 * id to quote, and a retry only when retrying could plausibly help.
 */
export function ErrorAlert({ error, title = "That could not be loaded", onRetry }: {
  error: unknown; title?: string; onRetry?: () => void;
}) {
  const api = error instanceof ApiError ? error : null;
  const message = api?.message ?? (error instanceof Error ? error.message : String(error));
  const retry = onRetry && (!api || api.transient);
  return (
    <Alert
      type={api && !api.transient ? "warning" : "error"}
      showIcon
      title={title}
      description={
        <>
          <div>{message}</div>
          {api?.requestId && (
            <Typography.Text type="secondary" style={{ fontSize: 12 }} copyable={{ text: api.requestId }}>
              Request {api.requestId.slice(0, 12)}
            </Typography.Text>
          )}
        </>
      }
      action={retry ? <Button size="small" onClick={onRetry}>Retry</Button> : undefined}
    />
  );
}
