import { Eye, EyeOff } from "lucide-react";
import { forwardRef, useState } from "react";
import type { ComponentPropsWithoutRef } from "react";

type PasswordInputProps = Omit<
  ComponentPropsWithoutRef<"input">,
  "type"
>;

export const PasswordInput = forwardRef<HTMLInputElement, PasswordInputProps>(
  function PasswordInput(props, ref) {
    const [visible, setVisible] = useState(false);

    return (
      <span className="password-input-wrap">
        <input {...props} ref={ref} type={visible ? "text" : "password"} />
        <button
          aria-label={visible ? "Hide password" : "Show password"}
          aria-pressed={visible}
          className="password-visibility-button"
          onClick={() => setVisible((current) => !current)}
          type="button"
        >
          {visible ? <EyeOff size={16} /> : <Eye size={16} />}
        </button>
      </span>
    );
  },
);

PasswordInput.displayName = "PasswordInput";
