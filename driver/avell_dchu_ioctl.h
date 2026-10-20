/* SPDX-License-Identifier: GPL-2.0-or-later WITH Linux-syscall-note */
/*
 * Raw _DSM access to \_SB.DCHU for diagnostics (root only).
 * Mirrors InsydeDCHU.dll: command = _DSM function index, in = 256 byte
 * Arg3 buffer, out = returned buffer (or integer in little endian).
 */
#ifndef _AVELL_DCHU_IOCTL_H
#define _AVELL_DCHU_IOCTL_H

#ifdef __KERNEL__
#include <linux/types.h>
#include <linux/ioctl.h>
#else
#include <stdint.h>
#include <sys/ioctl.h>
typedef uint8_t __u8;
typedef uint32_t __u32;
typedef uint64_t __u64;
#endif

struct avell_dchu_call {
	__u32 command;
	__u32 out_len;
	__u64 out_int;
	__u8 in[256];
	__u8 out[256];
};

#define AVELL_DCHU_IOC_CALL	_IOWR('A', 0x01, struct avell_dchu_call)

#endif
