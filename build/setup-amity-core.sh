#!/bin/bash

# This script is idempotent

set -xe

NAME=amity
ROOT_DIR=~
APP_DIR=$ROOT_DIR/$NAME

FIRMWARE_PATH=/boot/firmware

# Install dependencies
instpkgs()
{
  local i
  local PKGS

  PKGS=("$@")
  for i in ${!PKGS[@]}; do
    sudo apt-get -y install "${PKGS[i]}"
  done
}

sudo apt-get -y update

instpkgs bluez bluez-tools build-essential git libglib2.0-dev libbluetooth-dev python3-dev unzip vim
instpkgs libavahi-compat-libdnssd-dev libssl-dev

# Prevent keyboard power keys from rebooting or shutting down the machine
if [ ! -f /etc/systemd/logind.conf.d/disable-power-key.conf ]; then
    sudo mkdir -p /etc/systemd/logind.conf.d/
    TEMP_CONF_PATH=`mktemp`
    chmod 644 $TEMP_CONF_PATH
cat > "$TEMP_CONF_PATH" << EOF
[Login]
HandlePowerKey=ignore
EOF
    sudo cp $TEMP_CONF_PATH /etc/systemd/logind.conf.d/disable-power-key.conf
    sudo systemctl restart systemd-logind
fi

# Add overlay to config.txt, if necessary
CONFIG_TXT_PATH="$FIRMWARE_PATH/config.txt"
if ! grep -q "cec-gpio" "$CONFIG_TXT_PATH"; then
    TEMP_CONFIG_TXT_PATH=`mktemp`
    cp "$CONFIG_TXT_PATH" "$TEMP_CONFIG_TXT_PATH"
    sudo cat >> "$TEMP_CONFIG_TXT_PATH" << EOF

dtoverlay=cec-gpio

EOF
    sudo fsck -y "$FIRMWARE_PATH" || true
    sudo mount "$FIRMWARE_PATH" --options remount,rw
    sudo cp "$CONFIG_TXT_PATH" "$CONFIG_TXT_PATH".$NAME.backup
    sudo cp "$TEMP_CONFIG_TXT_PATH" "$CONFIG_TXT_PATH"
    sudo mount "$FIRMWARE_PATH" --options remount,ro
fi

# Disable userconfig service so it doesn't prompt to create a user on first boot, if no password
# or SSH public key was specified when burning the image.
sudo systemctl disable userconfig
sudo systemctl enable getty@tty1

# App setup

cd "$APP_DIR"

VAR_DIR=$APP_DIR/var
LOG_DIR=$VAR_DIR/log
CONFIG_DIR=$VAR_DIR/config
GUI_DIR=$VAR_DIR/gui
NICEGUI_DIR=$GUI_DIR/nicegui
HOMEKIT_DIR=$VAR_DIR/homekit

mkdir -p "$LOG_DIR"
mkdir -p "$CONFIG_DIR"
touch "$CONFIG_DIR/config.yaml"
mkdir -p "$GUI_DIR"
mkdir -p "$NICEGUI_DIR"
mkdir -p "$HOMEKIT_DIR"

# Create, and install cec-gpio overlay
DTB_NAME=cec-gpio.dtbo
DTB_DIR="$FIRMWARE_PATH/overlays"
DTB_PATH=$DTB_DIR/$DTB_NAME

if [ ! -f "$DTB_PATH" ]; then
    ./configure_gpio internal
fi

# Activate venv, and pip install requirements
. ./bin/activate
pip install --upgrade -r requirements.txt

# Allow python to bind to privileged network ports
sudo setcap 'cap_net_bind_service=+ep' $(readlink -f $(which python))

# Clone, build, and install our custom version of bluepy3
cd "$ROOT_DIR"
if [ ! -d "$ROOT_DIR/bluepy3" ]; then
    git clone https://github.com/retsyx/bluepy3
else
    pushd bluepy3
    git stash # cleanup bluepy3 build droppings
    git fetch && git rebase
    popd
fi

cd bluepy3
pip install .

# Setup .bashrc
if ! grep -q "# Amity" "$ROOT_DIR/.bashrc"; then

    cat >> "$ROOT_DIR/.bashrc" << EOF

# Amity
echo "Amity..."
cd "$APP_DIR" > /dev/null
. bin/activate
export PYTHONPATH=$APP_DIR

EOF

. $ROOT_DIR/.bashrc

fi

# User services directory

mkdir -p ~/.config/systemd/user

# Install the warmup service

RUN_PATH=$APP_DIR/bin/run-amity-warmup.sh

cat > "$RUN_PATH" << EOF
#!/bin/bash

# Create a self signed certificate that is valid for 100 years
if [ ! -f "$GUI_DIR/key.pem" ]; then
    /usr/bin/openssl req -x509 -newkey rsa:4096 -keyout "$GUI_DIR/key.pem" -out "$GUI_DIR/cert.pem" -sha256 -days 36500 -nodes -subj "/CN=Amity"
fi

. ./bin/activate

python -c "import bluepy3.btle, cec, config, gestures, hdmi, hdmi_tool, homekit, homekit_tool, keyboard, memory, messaging, pair_tool, remote, remote_adapter, tools"
rm cec.log || true

EOF

chmod +x "$RUN_PATH"

cat > ~/.config/systemd/user/$NAME-warmup.service << EOF
[Unit]
Description=Amity warmup
After=network-online.target systemd-resolved.service
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=$RUN_PATH
RemainAfterExit=true
WorkingDirectory=$APP_DIR

[Install]
WantedBy=default.target
EOF

systemctl --user enable "$NAME-warmup"

# Install Amity services

# Hack equivalent of systemd command: loginctl enable-linger
sudo mkdir -p /var/lib/systemd/linger
sudo touch /var/lib/systemd/linger/pi

function install_service() {
    local name="$1"
    local binary="$2"
    local description="$3"

    local RUN_PATH="$APP_DIR/bin/run-$name.sh"

cat > "$RUN_PATH" << EOF
#!/bin/bash

. ./bin/activate

export PYTHONPATH="$APP_DIR"

$binary
EOF

chmod +x "$RUN_PATH"

cat > ~/.config/systemd/user/$name.service << EOF
[Unit]
Description=$description
After=$NAME-warmup.service
Requires=$NAME-warmup.service

[Service]
ExecStart=$RUN_PATH
Restart=always
WorkingDirectory=$APP_DIR

[Install]
WantedBy=default.target
EOF

systemctl --user enable "$name"

} # end install_service

install_service "$NAME-hub" "$APP_DIR/main.py" "$NAME HDMI-CEC controller"
install_service "$NAME-management" "$APP_DIR/management/main.py" "$NAME management"
install_service "$NAME-redirect" "$APP_DIR/management/redirect.py" "$NAME HTTP to HTTPS redirect"

# Install kernels

sudo mount "$FIRMWARE_PATH" --options remount,rw

for KERNEL_ARCHIVE in ${ROOT_DIR}/linux-build/out/kernel*.zip; do
    sudo unzip -o "$KERNEL_ARCHIVE" -d /
    BUILD="$(unzip -l ${KERNEL_ARCHIVE} boot/vmlinuz-* | sed -n 's|^.*boot/vmlinuz-\(.*\)$|\1|p')"
    sudo update-initramfs -c -v -k "${BUILD}"
done

